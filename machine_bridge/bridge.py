"""
DNJ Machine Bridge
==================
Reads machine list from Odoo → pings each machine → optionally reads
Modbus TCP registers → pushes results back to Odoo every POLL_INTERVAL s.

Machine configuration lives in Odoo:
  DNJ Shopfloor → Configuration → Machine Monitoring

Usage:
    python bridge.py            # single round and exit
    python bridge.py --loop     # continuous polling (production mode)
    python bridge.py --test     # test connection to Odoo and exit
"""

import argparse
import json
import logging
import platform
import socket
import struct
import subprocess
import time
import urllib.request

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── ICMP ping ─────────────────────────────────────────────────────────────────

def ping(ip: str, timeout: int = config.PING_TIMEOUT) -> tuple[bool, int]:
    """Ping via subprocess. Returns (online, response_ms)."""
    if not ip:
        return False, 0
    is_win = platform.system().lower() == "windows"
    cmd = (["ping", "-n", "1", "-w", str(timeout * 1000), ip]
           if is_win else ["ping", "-c", "1", "-W", str(timeout), ip])
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout + 1)
        ms = int((time.monotonic() - t0) * 1000)
        return r.returncode == 0, ms if r.returncode == 0 else 0
    except (subprocess.TimeoutExpired, OSError):
        return False, 0


# ── Modbus TCP (stdlib only — no pymodbus) ────────────────────────────────────

class ModbusClient:
    """
    Minimal Modbus TCP client using raw sockets.
    Reads holding registers (function code 0x03).
    No external dependencies.
    """

    def __init__(self, ip: str, port: int = 502,
                 timeout: float = config.MODBUS_TIMEOUT):
        self.ip = ip
        self.port = port
        self.timeout = timeout

    def _request(self, start_reg: int, count: int) -> list[int] | None:
        """Send read-holding-registers request, return list of register values."""
        # Modbus TCP ADU: transaction_id(2) + protocol(2) + length(2) + unit(1) + pdu
        pdu = struct.pack(">BHH", 0x03, start_reg, count)   # FC03 + addr + qty
        header = struct.pack(">HHHB", 1, 0, len(pdu) + 1, 1)
        request = header + pdu
        try:
            with socket.create_connection((self.ip, self.port),
                                          timeout=self.timeout) as s:
                s.sendall(request)
                raw = s.recv(256)
        except (OSError, socket.timeout):
            return None

        if len(raw) < 9:
            return None
        byte_count = raw[8]
        values = []
        for i in range(byte_count // 2):
            values.append(struct.unpack_from(">H", raw, 9 + i * 2)[0])
        return values

    def read_machine_state(self) -> dict | None:
        """
        Read standard register map (can be adjusted per machine):
          HR[0] = running status  (0=stopped, 1=running)
          HR[1] = speed           (sheets/hour)
          HR[2] = counter         (total sheets)
        Returns dict or None if unreachable.
        """
        regs = self._request(0, 3)
        if regs is None or len(regs) < 3:
            return None
        return {
            "machine_running": bool(regs[0]),
            "machine_speed":   regs[1],
            "machine_counter": regs[2],
        }


# ── Odoo JSON-RPC session ─────────────────────────────────────────────────────

class OdooSession:
    """Thin JSON-RPC client that keeps a session cookie."""

    def __init__(self):
        self._cookie: str | None = None

    def _call(self, path: str, params: dict) -> dict:
        payload = json.dumps({
            "jsonrpc": "2.0", "method": "call", "id": 1, "params": params,
        }).encode()
        req = urllib.request.Request(
            f"{config.ODOO_URL}{path}", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        if self._cookie:
            req.add_header("Cookie", self._cookie)
        with urllib.request.urlopen(req, timeout=15) as resp:
            cookie = resp.headers.get("Set-Cookie")
            if cookie:
                self._cookie = cookie.split(";")[0]
            body = json.loads(resp.read())
        if "error" in body:
            raise RuntimeError(body["error"])
        return body.get("result", {})

    def authenticate(self) -> bool:
        try:
            r = self._call("/web/session/authenticate", {
                "db": config.ODOO_DB,
                "login": config.ODOO_LOGIN,
                "password": config.ODOO_PASSWORD,
            })
            if r.get("uid"):
                log.info("Authenticated as %s (uid=%s)", config.ODOO_LOGIN, r["uid"])
                return True
            log.error("Auth rejected: %s", r)
            return False
        except Exception as e:
            log.error("Auth error: %s", e)
            return False

    def get_machine_config(self) -> list[dict]:
        """Fetch machine list + IP/Modbus config from Odoo."""
        try:
            return self._call("/dnj_shopfloor/machine/config", {})
        except Exception as e:
            log.warning("Could not load machine config: %s", e)
            return []

    def heartbeat(self, machines: list) -> dict:
        return self._call("/dnj_shopfloor/machine/heartbeat",
                          {"machines": machines})


# ── one poll round ────────────────────────────────────────────────────────────

def poll_once(session: OdooSession, machines: list[dict]) -> bool:
    """Ping (and optionally Modbus-read) all machines, push to Odoo."""
    if not machines:
        log.info("No machines configured — add entries in Odoo → Configuration → Machine Monitoring")
        return True

    payload = []
    for m in machines:
        ip   = m["ip_address"]
        name = m["name"]
        online, ms = ping(ip)

        entry = {
            "workcenter_id":  m["workcenter_id"],
            "online":         online,
            "response_ms":    ms,
            "machine_running": False,
            "machine_speed":   0,
            "machine_counter": 0,
        }

        if online and m.get("modbus_enabled"):
            client = ModbusClient(ip, port=m.get("modbus_port", 502))
            data = client.read_machine_state()
            if data:
                entry.update(data)
                log.info("  %-25s %-15s ONLINE  %dms  Modbus: running=%s speed=%d counter=%d",
                         name, ip, ms,
                         data["machine_running"], data["machine_speed"], data["machine_counter"])
            else:
                log.info("  %-25s %-15s ONLINE  %dms  Modbus: no response", name, ip, ms)
        else:
            status = "ONLINE " if online else "OFFLINE"
            ping_s = f"{ms}ms" if online else "timeout"
            log.info("  %-25s %-15s %s  %s", name, ip, status, ping_s)

        payload.append(entry)

    try:
        result = session.heartbeat(payload)
        log.info("Heartbeat → %s", result)
        return True
    except Exception as e:
        log.warning("Heartbeat failed: %s", e)
        return False


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DNJ Machine Bridge")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously every POLL_INTERVAL seconds")
    parser.add_argument("--test", action="store_true",
                        help="Test Odoo connection and print machine config, then exit")
    args = parser.parse_args()

    session = OdooSession()
    log.info("DNJ Machine Bridge — %s", config.ODOO_URL)

    if not session.authenticate():
        log.error("Cannot authenticate. Check config.py.")
        return

    machines = session.get_machine_config()
    log.info("Loaded %d machine(s) from Odoo", len(machines))
    for m in machines:
        modbus = f"  Modbus:{m['modbus_port']}" if m.get("modbus_enabled") else ""
        log.info("  [%d] %-25s  %s%s", m["workcenter_id"], m["name"],
                 m["ip_address"], modbus)

    if args.test:
        return

    if args.loop:
        config_reload_at = time.monotonic() + config.CONFIG_RELOAD
        while True:
            log.info("── Ping round ──────────────────────────────────")
            poll_once(session, machines)

            # Reload machine config periodically (admin may have changed IPs)
            if time.monotonic() >= config_reload_at:
                new = session.get_machine_config()
                if new is not None:
                    machines = new
                    log.info("Config reloaded: %d machine(s)", len(machines))
                config_reload_at = time.monotonic() + config.CONFIG_RELOAD

            time.sleep(config.POLL_INTERVAL)
    else:
        poll_once(session, machines)


if __name__ == "__main__":
    main()
