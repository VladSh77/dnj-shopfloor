"""
Machine Bridge configuration.
Only connection credentials and timing go here.
Machine list (IP addresses, Modbus settings) is configured in Odoo:
  DNJ Shopfloor → Configuration → Machine Monitoring
"""

# ── Odoo connection ───────────────────────────────────────────────────────────
ODOO_URL      = "https://dnj.fayna.agency"
ODOO_DB       = "dnj_demo"
ODOO_LOGIN    = "kiosk"
ODOO_PASSWORD = "Kiosk2024"

# ── Timing ────────────────────────────────────────────────────────────────────
POLL_INTERVAL   = 30   # seconds between ping/Modbus rounds
PING_TIMEOUT    = 2    # seconds per ICMP ping
MODBUS_TIMEOUT  = 3    # seconds per Modbus TCP connection
CONFIG_RELOAD   = 300  # seconds between re-reading machine list from Odoo
