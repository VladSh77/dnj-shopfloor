# DNJ Shop Floor Kiosk — Technical Reference

**Module:** `dnj_shopfloor`
**Odoo:** 17.0 Community
**Author:** Fayna Digital

---

## Architecture

```
Tablet (browser)                 Odoo Server
────────────────                 ──────────────────────────────
/kiosk  ──────────────────────►  HTTP route (auth=none)
                                   auto-login as kiosk user
                                   redirect → /web#action=...
                                              │
OWL App: DnjShopfloorKiosk ◄─────────────────┘
  PinScreen
  WorkcenterSelector           JSON-RPC endpoints
  WorkOrderQueue          ◄──► /dnj_shopfloor/authenticate
  TestPrintScreen         ◄──► /dnj_shopfloor/session/open
  WorkScreen              ◄──► /dnj_shopfloor/session/action
  PauseModal              ◄──► /dnj_shopfloor/session/status
                          ◄──► /dnj_shopfloor/workorders
                          ◄──► /dnj_shopfloor/workcenters

OWL App: DnjShopfloorDashboard
  MachineCard             ◄──► /dnj_shopfloor/dashboard
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
Stores operator PIN credentials.

| Field         | Type    | Notes                                  |
|---------------|---------|----------------------------------------|
| `name`        | Char    |                                        |
| `pin_hash`    | Char    | SHA-256 of PIN                         |
| `active`      | Boolean |                                        |

**Method:** `authenticate(pin, workcenter_id)` — hashes PIN, returns `{success, operator_id, name}` or `{success: False, error}`.

### `dnj.kiosk.session`
One row per operator login on a machine.

| Field            | Type        | Notes                              |
|------------------|-------------|------------------------------------|
| `operator_id`    | Many2one    | `dnj.operator`                     |
| `workcenter_id`  | Many2one    | `mrp.workcenter`                   |
| `workorder_id`   | Many2one    | `mrp.workorder` (nullable)         |
| `state`          | Selection   | `active → confirmed → progress → paused → done` |
| `work_start_time`| Datetime    | set on `action_start_work()`       |
| `qty_produced`   | Float       |                                    |
| `qty_scrap`      | Float       |                                    |
| `pause_ids`      | One2many    | `dnj.kiosk.pause`                  |

**Lifecycle methods:** `action_start_test_print`, `action_confirm_machine`, `action_start_work`, `action_pause`, `action_resume`, `action_stop_work`, `action_logout`.

### `dnj.kiosk.pause`
Tracks each pause interval.

| Field              | Type     |
|--------------------|----------|
| `session_id`       | Many2one |
| `reason`           | Char     |
| `start_time`       | Datetime |
| `end_time`         | Datetime |
| `duration_minutes` | Float    | computed

---

## API Endpoints

### `POST /dnj_shopfloor/authenticate`
```json
Request:  { "pin": "1234", "workcenter_id": 3 }
Response: { "success": true, "operator_id": 7, "name": "Jan Kowalski" }
          { "success": false, "error": "Nieprawidłowy PIN" }
```

### `POST /dnj_shopfloor/session/open`
```json
Request:  { "operator_id": 7, "workcenter_id": 3 }
Response: { "session_id": 42, "state": "active" }
```

### `POST /dnj_shopfloor/session/action`
```json
Request:  { "session_id": 42, "action": "start_work" }
          { "session_id": 42, "action": "pause", "reason": "coffee" }
          { "session_id": 42, "action": "stop", "qty_produced": 500, "qty_scrap": 3 }
Response: { "success": true, "state": "progress" }
```
Actions: `test_print | confirm_machine | select_workorder | start_work | pause | resume | stop | logout`

### `POST /dnj_shopfloor/session/status`
```json
Request:  { "session_id": 42 }
Response: { "found": true, "state": "progress", "work_start_time": "2026-03-24T08:00:00",
            "pause_minutes": 15.0, "qty_produced": 200, "qty_scrap": 1 }
```

### `POST /dnj_shopfloor/workorders`
```json
Request:  { "workcenter_id": 3 }
Response: [ { "id": 11, "name": "WO/00011", "state": "ready",
              "production_id": [5, "MO/00005"], "product_id": [8, "Ulotka A4"],
              "qty_production": 1000, "qty_produced": 0, "date_start": "2026-03-24T06:00:00" } ]
```

### `POST /dnj_shopfloor/workcenters`
```json
Response: [ { "id": 1, "name": "HSM-XL", "code": "HSM" }, ... ]
```

### `POST /dnj_shopfloor/dashboard`
```json
Response: [ { "id": 1, "name": "HSM-XL", "code": "HSM",
              "session": { "id": 42, "state": "progress",
                           "operator": "Jan Kowalski", "workorder": "WO/00011",
                           "product": "Ulotka A4 / 4+0",
                           "qty_produced": 200, "qty_scrap": 1, "qty_production": 1000,
                           "work_start": "2026-03-24T08:00:00", "pause_minutes": 15.0 } } ]
```
`session` is `null` when the machine is idle.

### `GET /kiosk`
Tablet entry point. Auto-logs in as the shared kiosk Odoo user (configurable via `ir.config_parameter`), then redirects to the kiosk OWL action. Open this URL on tablets — no manual Odoo login needed.

---

## Frontend (OWL 2)

### Kiosk app — `static/src/js/kiosk_app.js`
Root: `DnjShopfloorKiosk` (registered as action `dnj_shopfloor_kiosk_action`).
Template: `static/src/xml/kiosk_template.xml`.

**Timer persistence** — on every state change the session is saved to `localStorage` under key `dnj_kiosk_session`. On startup, `_tryRestoreSession()` reads this, polls `/session/status`, and if the session is still active jumps straight to the WorkScreen with the timer already running from the correct elapsed time. This survives page reloads and tablet restarts.

### Dashboard app — `static/src/js/dashboard_app.js`
Root: `DnjShopfloorDashboard` (registered as action `dnj_shopfloor_dashboard_action`).
Template: `static/src/xml/dashboard_template.xml`.
Polls `/dnj_shopfloor/dashboard` every 30 s; a 1 s tick drives live timers on each `MachineCard`.

---

## Kiosk User Setup

The tablet needs a single shared Odoo user that stays permanently logged in.

```python
# Run once in Odoo shell:
env['res.users'].create({
    'name': 'Kiosk Tablet',
    'login': 'kiosk',
    'password': 'Kiosk2024',
    'groups_id': [(6, 0, [env.ref('base.group_user').id])],
})
```

Credentials can be changed in **Settings → Technical → System Parameters**:
- `dnj_shopfloor.kiosk_login`
- `dnj_shopfloor.kiosk_password`

---

## Operator PIN Setup

Add operators in **Shop Floor → Operators**. PIN is stored as SHA-256 hash. Default demo PIN for all operators: **1234**.

To hash a PIN manually:
```python
import hashlib
hashlib.sha256("1234".encode()).hexdigest()
# → 03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4
```

---

## Deploy

```bash
# 1. Push code
git push

# 2. On server (~/dnj-demo)
git pull

# 3. Update module (required after any XML/model changes)
docker compose run --rm web odoo -u dnj_shopfloor -d <db_name> --stop-after-init

# 4. Restart
docker compose restart web
```

JavaScript/CSS changes (no XML/model changes) only need step 4 + hard-refresh in the browser.

---

## Brand

| Token   | Hex       | Usage                     |
|---------|-----------|---------------------------|
| Gold    | `#C9A227` | Accent, headers, badges   |
| Green   | `#2D5C2D` | Active/progress state     |
| Dark BG | `#111209` | Page background           |
| Card    | `#1C1C12` | Card / panel background   |
| Border  | `#333320` | Subtle dividers           |
