"""
DNJ Machine Bridge
==================
Pings each configured machine, then pushes online/offline status
to Odoo via /dnj_shopfloor/machine/heartbeat (JSON-RPC).

Usage:
    python bridge.py                # run once and exit
    python bridge.py --loop         # run every POLL_INTERVAL seconds
"""

import argparse
import json
import logging
import platform
import subprocess
import time
import urllib.request
import urllib.error

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── ping ─────────────────────────────────────────────────────────────────────

def ping(ip: str, timeout: int = config.PING_TIMEOUT) -> tuple[bool, int]:
    """
    ICMP ping via subprocess.
    Returns (online: bool, response_ms: int).
    """
    if not ip:
        return False, 0

    is_windows = platform.system().lower() == "windows"
    cmd = (
        ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
        if is_windows
        else ["ping", "-c", "1", "-W", str(timeout), ip]
    )

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        online = result.returncode == 0
        return online, elapsed_ms if online else 0
    except (subprocess.TimeoutExpired, OSError):
        return False, 0


# ── Odoo JSON-RPC session ─────────────────────────────────────────────────────

class OdooSession:
    """Thin JSON-RPC client that keeps a session cookie for auth."""

    def __init__(self, url: str, db: str, login: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.login = login
        self.password = password
        self._cookie: str | None = None

    def _call(self, path: str, params: dict) -> dict:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method":  "call",
            "id":      1,
            "params":  params,
        }).encode()

        req = urllib.request.Request(
            f"{self.url}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._cookie:
            req.add_header("Cookie", self._cookie)

        with urllib.request.urlopen(req, timeout=10) as resp:
            # persist session cookie
            raw_cookie = resp.headers.get("Set-Cookie")
            if raw_cookie:
                self._cookie = raw_cookie.split(";")[0]
            body = json.loads(resp.read())

        if "error" in body:
            raise RuntimeError(body["error"])
        return body.get("result", {})

    def authenticate(self) -> bool:
        try:
            result = self._call("/web/session/authenticate", {
                "db":       self.db,
                "login":    self.login,
                "password": self.password,
            })
            ok = bool(result.get("uid"))
            if ok:
                log.info("Authenticated as %s (uid=%s)", self.login, result["uid"])
            else:
                log.error("Authentication failed: %s", result)
            return ok
        except Exception as e:
            log.error("Auth error: %s", e)
            return False

    def heartbeat(self, machines: list) -> dict:
        return self._call("/dnj_shopfloor/machine/heartbeat", {"machines": machines})


# ── main loop ─────────────────────────────────────────────────────────────────

def run_once(session: OdooSession):
    payload = []
    for m in config.MACHINES:
        ip = m.get("ip_address")
        online, ms = ping(ip)
        status = "ONLINE" if online else "OFFLINE"
        ping_str = f"{ms}ms" if online else "timeout"
        log.info("  %-25s %-15s %s  %s", m["name"], ip or "(no IP)", status, ping_str)
        payload.append({
            "workcenter_id": m["workcenter_id"],
            "ip_address":    ip or "",
            "online":        online,
            "response_ms":   ms,
        })

    try:
        result = session.heartbeat(payload)
        log.info("Heartbeat sent → %s", result)
    except Exception as e:
        log.warning("Heartbeat failed: %s — re-authenticating…", e)
        if session.authenticate():
            try:
                result = session.heartbeat(payload)
                log.info("Heartbeat sent (retry) → %s", result)
            except Exception as e2:
                log.error("Retry failed: %s", e2)


def main():
    parser = argparse.ArgumentParser(description="DNJ Machine Bridge")
    parser.add_argument("--loop", action="store_true",
                        help="Keep running every POLL_INTERVAL seconds")
    args = parser.parse_args()

    session = OdooSession(config.ODOO_URL, config.ODOO_DB,
                          config.ODOO_LOGIN, config.ODOO_PASSWORD)

    log.info("DNJ Machine Bridge starting — target: %s", config.ODOO_URL)
    log.info("Monitoring %d machine(s), interval=%ds", len(config.MACHINES), config.POLL_INTERVAL)

    if not session.authenticate():
        log.error("Cannot authenticate — check config.py credentials.")
        return

    if args.loop:
        while True:
            log.info("── Ping round ─────────────────────────────")
            run_once(session)
            time.sleep(config.POLL_INTERVAL)
    else:
        run_once(session)


if __name__ == "__main__":
    main()
