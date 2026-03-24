"""
Machine Bridge configuration.
Edit these values before deploying.
"""

# ── Odoo connection ───────────────────────────────────────────────────────────
ODOO_URL      = "https://dnj.fayna.agency"
ODOO_DB       = "dnj_demo"
ODOO_LOGIN    = "kiosk"
ODOO_PASSWORD = "Kiosk2024"

# ── Bridge behaviour ──────────────────────────────────────────────────────────
POLL_INTERVAL  = 30   # seconds between ping rounds
PING_TIMEOUT   = 2    # seconds per ping

# ── Machine definitions ───────────────────────────────────────────────────────
# workcenter_id: Odoo mrp.workcenter database ID
# ip_address:    network address to ICMP-ping
# If IP is None, the machine is skipped (not monitored).
MACHINES = [
    {"workcenter_id": 1, "name": "Heidelberg XL-106", "ip_address": "8.8.8.8"},
    {"workcenter_id": 2, "name": "HP Indigo 6K",       "ip_address": "1.1.1.1"},
]
