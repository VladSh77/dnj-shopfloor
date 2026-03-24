# DNJ Shop Floor Kiosk — Technical Reference

**Module:** `dnj_shopfloor`
**Odoo:** 17.0 Community
**Author:** Fayna Digital

---

## Architecture

```
Tablet (browser)                 Odoo Server                    Machine Bridge
────────────────                 ──────────────────────────      ──────────────
/kiosk  ──────────────────────►  HTTP route (auth=none)
                                   auto-login as kiosk user
                                   redirect → /web#action=...
                                              │
OWL App: DnjShopfloorKiosk ◄─────────────────┘
  PinScreen                     JSON-RPC endpoints
  WorkcenterSelector        ◄──► /authenticate
  WorkOrderQueue            ◄──► /session/open
  TestPrintScreen           ◄──► /session/action
  WorkScreen                ◄──► /session/status
  PauseModal                ◄──► /workorders
                            ◄──► /workcenters

OWL App: DnjShopfloorDashboard
  MachineCard               ◄──► /dashboard (incl. machine_status)
                                              ▲
                                              │ heartbeat every 30s
                                  /machine/heartbeat ◄─── bridge.py (Docker)
                                  /machine/config    ──►  bridge.py (reads config)
                                                           │
                                                     ICMP ping + Modbus TCP
                                                           │
                                                     Factory machines
```

---

## Screen Flow (Kiosk)

```
machine → pin → queue → test_print → (confirm) → work
                  ▲                                 │
                  └──────── logout ◄────────────────┤
                                                    ├─ pause → resume
                                                    └─ stop  → queue
```

---

## Models

### `dnj.operator`

| Field           | Type    | Notes                                     |
|-----------------|---------|-------------------------------------------|
| `name`          | Char    |                                           |
| `pin_hash`      | Char    | SHA-256 of PIN                            |
| `workcenter_ids`| M2M     | `mrp.workcenter`                          |
| `active`        | Boolean |                                           |
| `session_count` | Integer | computed                                  |
| `last_session_date` | Datetime | computed                              |

**Method:** `authenticate(pin, workcenter_id)` — hashes PIN, returns `{success, operator_id, name}`.

---

### `dnj.kiosk.session`

One row per operator login on one machine.

| Field              | Type      | Notes                                          |
|--------------------|-----------|------------------------------------------------|
| `operator_id`      | Many2one  | `dnj.operator`                                 |
| `workcenter_id`    | Many2one  | `mrp.workcenter`                               |
| `workorder_id`     | Many2one  | `mrp.workorder` (nullable)                     |
| `state`            | Selection | `active→test_print→confirmed→progress→paused→done` |
| `start_time`       | Datetime  | login time                                     |
| `end_time`         | Datetime  | logout time                                    |
| `work_start_time`  | Datetime  | set on `action_start_work()`                   |
| `work_end_time`    | Datetime  | set on `action_stop_work()`                    |
| `test_print_qty`   | Float     |                                                |
| `qty_produced`     | Float     |                                                |
| `qty_scrap`        | Float     |                                                |
| `pause_ids`        | One2many  | `dnj.kiosk.pause`                              |
| `log_ids`          | One2many  | `dnj.workorder.log`                            |
| `duration_total`   | Float     | computed (minutes)                             |
| `duration_net`     | Float     | computed (total minus pauses)                  |

**Lifecycle methods:** `action_start_test_print(qty)`, `action_confirm_machine()`, `action_start_work()`, `action_pause(reason)`, `action_resume()`, `action_stop_work(qty_produced, qty_scrap)`, `action_logout()`.

---

### `dnj.kiosk.pause`

| Field              | Type     | Notes    |
|--------------------|----------|----------|
| `session_id`       | Many2one |          |
| `reason`           | Char     | `coffee \| maintenance \| material \| other` |
| `start_time`       | Datetime |          |
| `end_time`         | Datetime | set on resume |
| `duration_minutes` | Float    | computed |
| `note`             | Text     |          |

---

### `dnj.workorder.log`

Immutable event log.

| Field          | Type     | Notes                                                    |
|----------------|----------|----------------------------------------------------------|
| `session_id`   | Many2one |                                                          |
| `operator_id`  | Many2one |                                                          |
| `workcenter_id`| Many2one |                                                          |
| `workorder_id` | Many2one |                                                          |
| `event_type`   | Selection| `login\|logout\|test_print\|confirm_ready\|start\|pause\|resume\|stop\|error` |
| `timestamp`    | Datetime | auto                                                     |
| `qty`          | Float    |                                                          |
| `note`         | Text     |                                                          |

---

### `dnj.machine.status`

Network ping and Modbus status per workcenter.

**Admin-configurable fields** (set via UI: Configuration → Machine Monitoring):

| Field            | Type    | Notes                                          |
|------------------|---------|------------------------------------------------|
| `workcenter_id`  | Many2one| `mrp.workcenter` (unique)                      |
| `ip_address`     | Char    | IPv4 address on factory LAN                    |
| `modbus_enabled` | Boolean | Enable Modbus TCP polling                      |
| `modbus_port`    | Integer | Default: 502                                   |
| `notes`          | Text    | Model, register map, contact                   |

**Bridge-written fields** (updated by `machine_bridge` service, never overwritten by admin):

| Field             | Type     | Notes                              |
|-------------------|----------|------------------------------------|
| `online`          | Boolean  | Last ping result                   |
| `response_ms`     | Integer  | Ping latency                       |
| `last_check`      | Datetime | Timestamp of last poll             |
| `last_online`     | Datetime | Last time machine was reachable    |
| `machine_running` | Boolean  | HR[0] from Modbus                  |
| `machine_speed`   | Integer  | HR[1] from Modbus (sheets/hour)    |
| `machine_counter` | Integer  | HR[2] from Modbus (sheet counter)  |

---

## API Endpoints

All endpoints: `POST`, `Content-Type: application/json`, `auth='user'`.

---

### `GET /kiosk`
Tablet entry point. Auto-logs in as kiosk user, redirects to kiosk OWL action.
Credentials stored in `ir.config_parameter`:
- `dnj_shopfloor.kiosk_login` (default: `kiosk`)
- `dnj_shopfloor.kiosk_password` (default: `Kiosk2024`)

---

### `POST /dnj_shopfloor/authenticate`
```json
Request:  { "pin": "1234", "workcenter_id": 3 }
Response: { "success": true, "operator_id": 7, "name": "Jan Kowalski" }
          { "success": false, "error": "Nieprawidłowy PIN" }
```

---

### `POST /dnj_shopfloor/session/open`
```json
Request:  { "operator_id": 7, "workcenter_id": 3 }
Response: { "session_id": 42, "state": "active" }
```
Closes any existing non-done sessions for the same operator+workcenter.

---

### `POST /dnj_shopfloor/session/action`
```json
Request:  { "session_id": 42, "action": "start_work" }
          { "session_id": 42, "action": "pause", "reason": "coffee" }
          { "session_id": 42, "action": "stop", "qty_produced": 500, "qty_scrap": 3 }
Response: { "success": true, "state": "progress" }
          { "success": false, "error": "..." }
```
Actions: `test_print(qty)` | `confirm_machine` | `select_workorder(workorder_id)` | `start_work` | `pause(reason)` | `resume` | `stop(qty_produced, qty_scrap)` | `logout`

---

### `POST /dnj_shopfloor/session/status`
```json
Request:  { "session_id": 42 }
Response: { "found": true, "state": "progress",
            "work_start_time": "2026-03-24T08:00:00",
            "pause_minutes": 15.0,
            "qty_produced": 200, "qty_scrap": 1 }
          { "found": false }
```
Used by kiosk `_tryRestoreSession()` on page load.

---

### `POST /dnj_shopfloor/workorders`
```json
Request:  { "workcenter_id": 3 }
Response: [
  { "id": 11, "name": "WO/00011", "state": "ready",
    "production_id": [5, "MO/00005"], "product_id": [8, "Ulotka A4"],
    "qty_production": 1000, "qty_produced": 0,
    "date_start": "2026-03-24T06:00:00",
    "duration_expected": 120 }
]
```
`duration_expected` is in **minutes** (from `mrp.workorder`).

---

### `POST /dnj_shopfloor/workcenters`
```json
Response: [ { "id": 1, "name": "Heidelberg XL-106", "code": "HSM" }, ... ]
```

---

### `POST /dnj_shopfloor/dashboard`
```json
Response: [
  { "id": 1, "name": "Heidelberg XL-106", "code": "HSM",
    "session": {
      "id": 42, "state": "progress",
      "operator": "Jan Kowalski", "workorder": "WO/00011",
      "product": "Ulotka A4 / 4+0",
      "qty_produced": 200, "qty_scrap": 1, "qty_production": 1000,
      "duration_expected": 120,
      "work_start": "2026-03-24T08:00:00Z", "pause_minutes": 15.0
    },
    "machine_status": {
      "monitored": true, "online": true, "response_ms": 7,
      "last_check": "2026-03-24T09:30:00",
      "machine_running": true, "machine_speed": 12000, "machine_counter": 5500,
      "modbus_enabled": true
    }
  }
]
```
`session` is `null` when idle. `machine_status.monitored` is `false` when no IP configured.

---

### `POST /dnj_shopfloor/machine/config`
Called by bridge at startup and every `CONFIG_RELOAD` seconds.
```json
Response: [
  { "workcenter_id": 1, "name": "Heidelberg XL-106",
    "ip_address": "192.168.1.100",
    "modbus_enabled": true, "modbus_port": 502 }
]
```
Returns only records with a non-empty `ip_address`.

---

### `POST /dnj_shopfloor/machine/heartbeat`
Called by bridge after each poll round.
```json
Request: {
  "machines": [
    { "workcenter_id": 1, "online": true, "response_ms": 7,
      "machine_running": true, "machine_speed": 12000, "machine_counter": 5500 },
    { "workcenter_id": 2, "online": false, "response_ms": 0,
      "machine_running": false, "machine_speed": 0, "machine_counter": 0 }
  ]
}
Response: { "ok": true, "updated": 2 }
```
Only updates records that already exist (admin must create them). Never overwrites `ip_address`.

---

## Machine Bridge

Source: `machine_bridge/`

### `config.py`
Only Odoo credentials and timing. Machine list is fetched from Odoo.

```python
ODOO_URL      = "https://dnj.fayna.agency"
ODOO_DB       = "dnj_demo"
ODOO_LOGIN    = "kiosk"
ODOO_PASSWORD = "Kiosk2024"
POLL_INTERVAL   = 30    # seconds between ping rounds
PING_TIMEOUT    = 2     # seconds per ICMP ping
MODBUS_TIMEOUT  = 3     # seconds per Modbus TCP connection
CONFIG_RELOAD   = 300   # seconds between re-reading machine list from Odoo
```

### `bridge.py`

**Classes:**

`ModbusClient(ip, port, timeout)` — raw socket Modbus TCP client (no pymodbus).
- `read_machine_state()` → `{machine_running, machine_speed, machine_counter}` or `None`
- Reads HR[0], HR[1], HR[2] using function code 0x03

`OdooSession` — JSON-RPC client with session cookie.
- `authenticate()` → bool
- `get_machine_config()` → list of machine dicts
- `heartbeat(machines)` → response dict

**CLI:**
```bash
python bridge.py            # one round, exit
python bridge.py --loop     # continuous (production)
python bridge.py --test     # verify Odoo auth + print machine config, exit
```

### Modbus register map (default)

| Register | Meaning         | Notes                         |
|----------|-----------------|-------------------------------|
| `HR[0]`  | Running status  | 0 = stopped, 1 = running      |
| `HR[1]`  | Speed (sh/h)    | Sheets per hour               |
| `HR[2]`  | Sheet counter   | Total sheets since last reset |

To adjust for a specific machine, edit `ModbusClient.read_machine_state()` in `bridge.py`.

### Testing without a real machine

```bash
# Start Modbus simulator (Heidelberg XL-106 emulator):
cd /path/to/demo-industrial-iot
python plc_simulator.py
# → registers: HR[0]=1 (running), HR[1]=12000 (speed), HR[2]=5500 (counter)

# In Odoo: Machine Monitoring → set IP=127.0.0.1, Port=5020, Modbus=☑

# Run bridge test:
cd machine_bridge
python bridge.py --test
```

---

## Frontend (OWL 2)

### Kiosk — `static/src/js/kiosk_app.js`

Root: `DnjShopfloorKiosk` → action `dnj_shopfloor_kiosk_action`
Template: `static/src/xml/kiosk_template.xml`

**Components:** `WorkcenterSelector`, `PinScreen`, `WorkOrderQueue`, `TestPrintScreen`, `WorkScreen`, `PauseModal`

**Timer persistence** — on every state change the session is saved to `localStorage` key `dnj_kiosk_session`. On startup `_tryRestoreSession()` polls `/session/status` and reconstructs state (including elapsed timer) without operator re-login.

**Time bar** — motivational progress bar in WorkScreen:
- Width = `timerSec / (duration_expected * 60) * 100%`
- Color: green → gold (>80%) → orange (>95%) → red (overtime)
- Solid green when no `duration_expected`

### Dashboard — `static/src/js/dashboard_app.js`

Root: `DnjShopfloorDashboard` → action `dnj_shopfloor_dashboard_action`
Template: `static/src/xml/dashboard_template.xml`

- Polls `/dashboard` every 30 s
- 1 s tick drives live timers in `MachineCard`
- Shows network dot (green/red) + ping ms per machine
- Shows Modbus data (running/speed/counter) when `modbus_enabled` and `online`

---

## Kiosk User Setup

```python
# Run once in Odoo shell (or create via Settings → Users):
env['res.users'].create({
    'name': 'Kiosk Tablet',
    'login': 'kiosk',
    'password': 'Kiosk2024',
    'groups_id': [(6, 0, [env.ref('base.group_user').id])],
})
```

---

## Operator PIN

PINs stored as SHA-256. To hash manually:
```python
import hashlib
hashlib.sha256("1234".encode()).hexdigest()
# → 03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4
```

---

## Deploy

```bash
# JS/XML only (no model changes):
git pull && docker compose restart web

# Model or view changes:
docker compose stop web
docker compose run --rm web odoo -u dnj_shopfloor -d dnj_demo --stop-after-init \
  -r odoo -w odoo_secret_password
docker compose start web

# Bridge changes:
cd machine_bridge && docker compose up -d --build
```

---

## Brand tokens

| Token   | Hex       | Usage                       |
|---------|-----------|-----------------------------|
| Gold    | `#C9A227` | Accent, headers, badges     |
| Green   | `#2D5C2D` | Active/progress state       |
| Dark BG | `#111209` | Page background             |
| Card    | `#1C1C12` | Card / panel background     |
| Border  | `#333320` | Subtle dividers             |
