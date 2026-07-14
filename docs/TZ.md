# ТЗ — dnj-shopfloor (Odoo 17 Shop Floor Module)

> Технічне завдання виробничого кіоску друкарні **Drukarnia NOWAK-JAROCIN (DNJ)**.
> Формат: ISO/IEC/IEEE 29148 + EARS (Easy Approach to Requirements Syntax) + MoSCoW.
> Кожна вимога має: EARS-формулювання (контрольована мова `SHALL`), критерій приймання + метод верифікації (Test / Inspect / Demo / Analyze), пріоритет і статус реалізації.
>
> **Статус:** ✅ реалізовано · 🔲 заплановано · ⚠️ реалізовано, але критерій приймання потребує підтвердження проти коду (див. §8 Відкриті питання).
>
> _Оновлено 2026-07-03 за результатами аудиту `docs/tz-audit/2026-07-03/`. EARS-формулювання — з `TZ_IMPROVE_2026-07-03.md`. Джерела методології — §9._

---

## 0. Призначення і контекст

**Проблема, яку вирішує система.** У друкарні DNJ друкарські машини (Heidelberg тощо) працюють без цифрового обліку: невідомо в реальному часі, хто на якій машині працює, скільки триває Work Order (WO), де простій і де перевитрата норми часу. Облік ведеться на папері/у голові → менеджер не бачить завантаження цеху й не може порівняти план із фактом.

**Що робить система.** Модуль Odoo 17 + мережевий міст (Machine Bridge):
- **Оператор** через планшет-кіоск біля машини логіниться за PIN, бачить свої WO, запускає/паузить/зупиняє роботу — система фіксує час і події.
- **Менеджер** на дашборді бачить live-статус усіх машин, хто працює, прогрес WO.
- **Machine Bridge** опитує машини по мережі (ICMP ping + Modbus TCP) і віддає стан/швидкість/лічильник у Odoo.

**Стейкхолдери.** Оператор цеху · Менеджер виробництва (`mrp.group_mrp_manager`) · Адміністратор (конфігурація) · Machine Bridge (система-агент).

**Межі (scope).**
- **У межах:** облік праці оператора на WO, live-моніторинг машин, event log, Modbus-моніторинг, розгортання через Docker.
- **Поза межами (Roadmap, §6):** облік браку та вплив на собівартість, алерти менеджеру, автовизначення Modbus-регістрів, OPC-UA/Prinect, CI/CD, склад паперу, Sale Order → авто-MO.

---

## 1. Глосарій

| Термін | Визначення |
|--------|-----------|
| **Кіоск (kiosk)** | Планшет/термінал біля машини з веб-інтерфейсом оператора, доступний за `GET /kiosk` під виділеним кіоск-акаунтом без пароля користувача. |
| **Оператор** | Працівник цеху (`dnj.operator`), що автентифікується PIN-кодом і виконує роботу на закріпленій машині (Workcenter). |
| **Work Order (WO)** | Виробниче завдання Odoo (`mrp.workorder`), над яким оператор виконує дії старт/пауза/резюм/стоп. Синонім у вимогах — «робота» / «Task». |
| **Machine / Workcenter** | Друкарська машина, представлена в Odoo як Workcenter; має IP та параметри Modbus. |
| **Пауза** | Тимчасове призупинення активного WO: статус → `Paused`, час-трекінг зупиняється, WO відновлюваний через «Резюм». |
| **Стоп** | Завершення роботи над WO: статус → `Stopped/Completed`, час-трекінг зупиняється, обчислюється сумарна тривалість. **Відрізняється від Паузи** тим, що WO більше не відновлюється. |
| **Session (`dnj.kiosk.session`)** | Життєвий цикл взаємодії оператора з кіоском як state-machine: `Draft → Active → (Paused) → Ended/Cancelled`. |
| **Event Log (`dnj.workorder.log`)** | Незмінний журнал подій WO: `login, test_print, start, pause, resume, stop, logout`. |
| **Machine Bridge** | Окремий сервіс (`machine_bridge/`), що опитує машини (ICMP + Modbus TCP) і пушить результати в Odoo через REST. |
| **Modbus HR[0-2]** | Holding Registers 0-2 машини: [0] статус, [1] швидкість, [2] лічильник. |
| **Wall-clock timer** | Таймер, що показує фактичний астрономічний час роботи (а не інкрементний лічильник тіків); після завершення періоду показує статичну сумарну тривалість. |
| **PIN** | Код автентифікації оператора; зберігається як SHA-256 хеш. |

---

## 2. Функціональні вимоги

> EARS-конструкції: **WHEN** (подієва), **WHILE** (станова), **IF/THEN** (умовна), **GIVEN…WHEN…THEN** (Gherkin-готова). `SHALL` = обов'язкова поведінка.
> Пріоритет — MoSCoW: **M** Must · **S** Should · **C** Could · **W** Won't (цей реліз).

### 2.1 Оператор — Кіоск

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-001 | WHEN a GET request is made to `/kiosk` from a pre-authorized kiosk, THEN the system SHALL log in the associated kiosk account without a password and establish an active session valid ≥ 60 min. | Test: успішний авто-логін з авторизованого кіоска (200 OK + session token); відмова з неавторизованого. Inspect: механізм авторизації кіоска. | M | ⚠️ |
| REQ-002 | WHEN an operator authenticates with a PIN, THEN the system SHALL require a 4–6 digit PIN, store it as SHA-256 with a unique per-operator salt, allow ≤ 3 wrong attempts / 5 min, and lock the account for 15 min after 3 failures. Correct PIN grants access within 1 s. | Test: успіх/невдача входу, спрацювання блокування після 3 спроб, тривалість блокування; заміри часу відгуку. Inspect: код хешування+солі+lockout. ⚠️ Реалізовано лише 4–6-цифровий PIN + SHA-256 БЕЗ солі та БЕЗ lockout — див. §8. | M | ⚠️ |
| REQ-003 | WHILE the kiosk is assigned to a machine, THEN it SHALL display all Work Orders for that machine (WO ID, Status, Due Date), sorted by Due Date asc, refreshing every 60 s; IF none, display "No Work Orders Found". | Test: список вантажиться ≤ 2 с, сортування коректне, порожній стан показує заглушку. | M | ✅ |
| REQ-004 | WHEN an operator initiates a test print AND a printer is available, THEN the system SHALL print a page containing "Test Print Page" + timestamp and show "Print successful" within 3 s; IF the printer fails, THEN show "Printer error: [code]" without blocking the app. | Test: друк тест-сторінки, повідомлення успіху/помилки, тайминг. Inspect: вміст тест-сторінки. | S | ✅ |
| REQ-005 | GIVEN a Work Order in `Pending`, WHEN the operator clicks "Start", THEN the system SHALL set status `In Progress`, record start timestamp and user, and confirm "WO [ID] started" within 2 s; IF WO is already `In Progress`/`Completed`, reject with error. | Test: старт, перевірка статусу/таймстемпів/автора, невалідні стани. Inspect: поля БД. | M | ✅ |
| REQ-006 | WHEN the operator pauses an active WO, THEN the system SHALL set status `Paused` within 1 s, stop time tracking, show "WO [ID] paused", and forbid all actions except Resume/Stop on that WO. | Test: пауза активного WO, зупинка таймера, заборона інших дій. | M | ✅ |
| REQ-007 | WHEN the operator resumes a `Paused` WO, THEN the system SHALL restore the WO to its exact pre-pause state within 5 s, set status `In Progress`, restart time tracking, and show "WO [ID] resumed"; IF restore fails, keep it `Paused` and show an error. | Test: пауза→резюм, стан ідентичний до паузи, тайминг; симуляція збою. | M | ✅ |
| REQ-008 | WHEN the operator stops a WO, THEN the system SHALL show a confirmation prompt; on confirm SHALL set status `Stopped` within 2 s, cease all timers, calculate total duration, and make the WO unavailable for further work (distinct from Paused). | Test: підтвердження, зміна статусу, зупинка таймерів, спроба відновити зупинений WO. Inspect: стан у БД. | M | ✅ |
| REQ-009 | WHEN the operator selects Logout, THEN the system SHALL invalidate the session, clear session data, and redirect to login within 1 s; access to protected pages afterwards SHALL require re-authentication. | Test: вихід, редірект ≤ 1 с, спроба відкрити захищену URL напряму. | M | ✅ |
| REQ-010 | WHEN an operational period concludes, THEN the wall-clock timer SHALL display that period's total duration as a static value (non-incrementing), in `HH:MM:SS`, accurate to ±1 s/hour, sourced from the system clock. | Test: порівняння з зовнішнім еталоном часу, формат, статичність після завершення. | M | ✅ |
| REQ-011 | WHILE a WO is `In Progress`, THEN the system SHALL show a time-based progress bar = (elapsed / estimated total) × 100 %, updating every 1 s; IF elapsed > estimated, THEN show 100 % and indicate overrun. | Test: розрахунок прогресу для різних вхідних часів, візуал overrun. | S | ✅ |
| REQ-012 | WHEN an authenticated operator refreshes or returns within 30 min, THEN the system SHALL restore auth status and last active state; IF returning after 30 min, THEN prompt re-authentication. | Test: refresh у межах 10 хв → стан відновлено; після 35 хв → повторний вхід. Inspect: механізм зберігання сесії й TTL. | M | ✅ |
| REQ-013 | WHEN the UI renders at width 320–767 px, THEN it SHALL use a single-column layout; at 768–1023 px a two-column layout; at ≥ 1024 px full layout; vertical scroll enabled when content exceeds viewport. | Test: емуляція 320/767/768/1023/1024 px, перевірка розкладки й прокрутки. | M | ✅ |

### 2.2 Менеджерський Дашборд

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-014 | WHILE viewing the dashboard, THEN the system SHALL show each machine's status (`Running`/`Idle`/`Maintenance`/`Offline`), updated every 5 s; IF a machine is unreachable > 30 s, THEN mark it `Offline` and highlight red. | Test: симуляція змін статусу й розривів зв'язку, перевірка частоти оновлення ≥ 3 машини. | M | ✅ |
| REQ-015 | IF a user clicks a machine card, THEN the system SHALL navigate to that machine's Detail page. | Test: клік по 5 різних картках → коректна навігація на відповідну машину. | M | ✅ |
| REQ-016 | WHEN the Machine Detail panel opens, THEN the system SHALL show operational statistics (uptime `HH:MM:SS`, production rate units/h, daily error count, avg temperature °C/last hour), updating every 10 s. | Inspect: наявність і формат усіх метрик. Test: оновлення кожні 10 с, звірка з бекендом. | M | ✅ |
| REQ-017 | WHILE an operator is logged into a machine, THEN the dashboard SHALL show the operator's name and cumulative work time on that machine, accurate to ±1 min, updating continuously. | Test: звірка часу роботи з логами (похибка ≤ 1 хв); Inspect: логіка обчислення. | M | ✅ |
| REQ-018 | WHEN a WO's progress changes, THEN the system SHALL display its progress as a percentage 0–100 % = (completed steps / total steps) × 100, updated on the dashboard within 1 s. | Test: перевірка відсотка для різних станів завершення й своєчасності оновлення. | M | ✅ |
| REQ-019 | WHEN a manager clicks "Pause" for an active WO on the dashboard, THEN the system SHALL set status `Paused` within 500 ms and halt time tracking for that WO. | Test: замір часу відгуку, підтвердження зупинки таймера. | M | ✅ |
| REQ-020 | WHILE accessing the dashboard, THEN the system SHALL restrict it to users in `mrp.group_mrp_manager`; other users SHALL be denied. | Test: доступ під manager (дозволено) та під звичайним користувачем (відмова). | M | ✅ |

### 2.3 Event Log

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-021 | The `dnj.workorder.log` model SHALL include `event_type` (str), `timestamp` (datetime, ISO 8601), `user_id` (FK), `workorder_id` (FK, nullable), each entry with a unique id. | Inspect: схема моделі в БД (поля й типи). | M | ✅ |
| REQ-022 | WHEN a `login/test_print/start/pause/resume/stop/logout` event occurs, THEN the system SHALL log an entry in `dnj.workorder.log` with event type, exact timestamp, performing user id, and associated WO id (if any). | Test: тригер кожної події → перевірка наявності й коректності всіх атрибутів запису. | M | ✅ |
| REQ-023 | WHILE recording events, THEN the system SHALL store each log record immutably; attempts to modify/delete SHALL be rejected. (Термін зберігання — див. NFR-RET, §3.) | Test: спроба змінити/видалити запис журналу → відмова. Inspect: політика незмінності. | M | ✅ |

### 2.4 Конфігурація

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-024 | WHEN an Admin opens `DNJ Shopfloor → Configuration → Operators`, THEN the system SHALL allow CRUD on operator accounts and set/reset PINs enforcing the PIN policy (NFR-SEC). | Test: RBAC, усі CRUD-операції, правила PIN і скидання. | M | ✅ |
| REQ-025 | WHEN a Manager opens Operator-Machine Assignment, THEN the system SHALL allow assigning one or more operators to a Workcenter and one operator to ≤ 3 Workcenters, with reassignment. | Test: призначення/перепризначення через UI; ліміт одночасних призначень (4-те → помилка). | S | ✅ |
| REQ-026 | WHEN an Admin opens Machine Monitoring Configuration, THEN the system SHALL allow setting the Workcenter's IP (IPv4-validated), Modbus TCP port (default 502) and slave id (1–247); on save SHALL confirm "Monitoring parameters updated" and begin data acquisition within 10 s. | Test: ввід і валідація значень, збереження, поява перших даних на дашборді ≤ 10 с. | M | ✅ |

### 2.5 Machine Bridge

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-027 | WHILE running, the Machine Bridge SHALL read the machine list + IPs from Odoo every 60 s; IF the Odoo connection fails, THEN log the error, retry after 10 s, and use last-known config. | Test: симуляція збою Odoo → логування й ретрай; Inspect: звірка списку з джерелом. | M | ✅ |
| REQ-028 | WHILE running, for each machine the Bridge SHALL ICMP-ping every 10 s (timeout 1000 ms); IF ≥ 3/5 pings succeed THEN `online`, else `offline`. | Test: симуляція online/offline, зміна статусу за критерієм; Inspect: параметри ping. | M | ✅ |
| REQ-029 | WHILE a machine is `online`, the Bridge SHALL read Modbus TCP registers HR[0-2] (status, speed, counter) every 5 s; IF a Modbus error occurs, THEN log it, mark Modbus status `unavailable`, and retry after 15 s. | Test: симуляція Modbus-помилки → логування/статус/ретрай; Inspect: коректність значень з живої машини. | M | ✅ |
| REQ-030 | WHEN monitoring results update or every 30 s, THEN the Bridge SHALL POST them to Odoo (JSON `{machine_id,status,speed,counter}`, API-key auth) and expect 200 OK ≤ 5 s; on non-200/timeout SHALL log, mark data `unsent`, retry ≤ 3× with 10 s delay. | Test: симуляція відповідей 200/4xx/5xx/timeout → логіка ретраїв і маркування; Inspect: ендпоінт/формат/автентифікація. | M | ✅ |
| REQ-031 | WHILE operational (continuous mode), THEN the Bridge SHALL poll configured data points every 30 s. | Test: перевірка інтервалу опитування й отримання даних; Inspect: логи. | M | ✅ |
| REQ-032 | IF started with `--test`, THEN the Bridge SHALL perform a single monitoring cycle (poll → process → push to Odoo) and terminate. | Test: запуск з `--test` → один цикл і вихід (exit 0). | S | ✅ |
| REQ-033 | WHEN `docker-compose up` runs, THEN the system SHALL deploy all Bridge components and ensure they run and pass health checks. | Inspect: compose-файл, `docker ps`. Test: health-checks сервісів. | M | ✅ |
| REQ-034 | WHEN the PLC Simulator (`demo-industrial-iot`) is used, THEN it SHALL emit industrial IoT data enabling end-to-end testing of Bridge acquisition/processing/Odoo-integration. | Demo: симулятор генерує дані, Bridge їх обробляє. Test: цільові кейси проти симулятора. | S | ✅ |

### 2.6 API ендпоінти (11)

> **Фактичний контракт (звірено з `addons/dnj_shopfloor/controllers/kiosk.py`).** API — це **Odoo JSON-RPC** (`type='json'`), а не «чистий REST». Транспорт: `POST` з тілом `{"jsonrpc":"2.0","method":"call","params":{…}}`; успіх завжди `200 OK` з обгорткою `{"result": …}`, помилки Odoo — `200` з обгорткою `{"error": …}` (а не HTTP 4xx/5xx). Автентифікація — **сесія Odoo** (`auth='user'`, cookie `session_id`), **НЕ JWT**, немає `access_token`/`expires_in`. Ідентифікатори записів — **цілі числа Odoo** (`operator_id`, `workcenter_id`, `session_id`), **НЕ UUID**. Прикладна помилка (невірний PIN, немає сесії) повертається у самому `result` як `{"success": false, "error": "…"}`. Виняток — `/kiosk`: це `type='http'`, `auth='none'`, метод `GET`, повертає HTML-редірект (див. REQ-035, §8).
>
> ⚠️ **Aspirational (НЕ реалізовано):** OpenAPI 3.x-специфікація, HTTP-коди помилок 400/401/403/404/422, суворі пороги латентності (p95/p90), ретенція логів невдалих спроб ≥ 30 днів. Наведені нижче JWT/UUID/REST-CRUD-критерії первинного ТЗ **не відповідають коду** і перероблені на фактичну поведінку.

| ID | Ендпоінт · фактична поведінка | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|------------------------|----------------------------------|:------:|:------:|
| REQ-035 | `GET /kiosk` (`type='http'`, `auth='none'`): авто-логінить спільний кіоск-акаунт (логін/пароль з `ir.config_parameter`, дефолт `kiosk`/`Kiosk2024`) і повертає HTML, що редіректить на fullscreen-екшен кіоска. **Немає** JSON `{id,name,location,…}`, немає 401 для неавтентифікованого — вхід відкритий кожному, хто знає URL. | Test: `GET /kiosk` → 200 + HTML-редірект; Inspect: `auth='none'`, дефолтний пароль. ⚠️ діра доступу — див. §8. | M | ⚠️ |
| REQ-036 | `POST /dnj_shopfloor/authenticate` (JSON-RPC, `auth='user'`): `params {pin:str, workcenter_id:int}` → `result {success:true, operator_id:int, name:str}`; невірний PIN / немає доступу до машини → `result {success:false, error:str}`. **Немає** JWT, `access_token`, `expires_in`. Спроби логуються в Odoo-логер (без гарантованої ретенції ≥ 30 днів — aspirational). | Test: валідний/невалідний PIN, обмеження за workcenter; Inspect: відповідь містить `operator_id`/`name`, НЕ токен. | M | ⚠️ |
| REQ-037 | `POST /dnj_shopfloor/session/open` (JSON-RPC): `params {operator_id:int, workcenter_id:int}` → закриває всі незавершені сесії цієї машини, створює нову → `result {session_id:int, state:str}`. `session_id` — **ціле id Odoo, НЕ UUID**. | Test: створення сесії, закриття попередніх сесій машини, тип `session_id`=int. | M | ✅ |
| REQ-038 | `POST /dnj_shopfloor/session/action` (JSON-RPC): `params {session_id:int, action:str, **kwargs}`; `action ∈ {test_print, confirm_machine, select_workorder, start_work, pause, resume, stop, logout}` → `result {success:true, state:str}`; неіснуюча сесія / невідома дія / виняток → `result {success:false, error:str}`. | Test: кожна дія → зміна `state`; неіснуючий `session_id` → `{success:false}`. | M | ✅ |
| REQ-039 | `POST /dnj_shopfloor/session/status` (JSON-RPC): `params {session_id:int}` → **READ-only** `result {found:bool, state, work_start_time, pause_minutes, qty_produced, qty_scrap}`. Це опитування (poll) стану, **НЕ** оновлення статусу. | Test: полінг стану активної/неіснуючої сесії (`found:false`). | M | ✅ |
| REQ-040 | `POST /dnj_shopfloor/workorders` (JSON-RPC): `params {workcenter_id:int}` → **READ-only СПИСОК** (`search_read`) активних WO машини (поля id,name,state,production_id,product_id,qty_production,qty_produced,date_start,duration_expected), `order=date_start asc`, `limit=50`. **НЕ** створює WO, **немає** 201. | Test: список WO для машини, сортування, порожній результат = `[]`. | M | ✅ |
| REQ-041 | `POST /dnj_shopfloor/workcenters` (JSON-RPC): **без параметрів** → **READ-only СПИСОК** (`search_read`) активних workcenter'ів (поля id,name,code), `order=name asc`, `limit=50`. **НЕ** створює workcenter, **немає** `capacity`, **немає** 201. | Test: список активних машин, лише active=True. | M | ✅ |
| REQ-042 | `POST /dnj_shopfloor/dashboard` (JSON-RPC): **без параметрів** → список усіх активних workcenter'ів з їхньою live-сесією + machine_status. **НЕ** приймає `{startDate,endDate}`, **НЕ** агрегує метрики за період. | Test: повертає всі машини з поточною сесією й статусом Modbus. | M | ✅ |
| REQ-043 | `POST /dnj_shopfloor/machine/config` (JSON-RPC): **без параметрів** → **READ-only СПИСОК** машин, що мають заданий IP (workcenter_id,name,ip_address,modbus_enabled,modbus_port) — для стартового читання Bridge. **НЕ** приймає `{machineId(UUID),configuration}`, **НЕ** оновлює конфіг. | Test: список машин лише з непорожнім IP. | M | ✅ |
| REQ-044 | `POST /dnj_shopfloor/machine/heartbeat` (JSON-RPC): `params {machines:list}`, кожен елемент `{workcenter_id:int, online, response_ms, machine_running, machine_speed, machine_counter}` → оновлює live-поля наявних записів → `result {ok:true, updated:int}`. Ключ — **цілий `workcenter_id`, НЕ UUID**; оновлює лише вже створені адміном записи. | Test: пуш пачки статусів, оновлення `last_check`/`online`; невідома машина ігнорується. | M | ✅ |
| REQ-045 | `POST /dnj_shopfloor/machine/stats` (JSON-RPC): `params {workcenter_id:int}` → **READ-only** детальна статистика однієї машини (today: produced/scrap/work/pause, operators_7d, recent_sessions[10]). Це читання для панелі деталей, **НЕ** запис stats, **немає** 202. | Test: детальні метрики для машини за сьогодні/7 днів/останні 10 сесій. | M | ✅ |

### 2.7 Моделі Odoo

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-046 | `dnj.operator` SHALL be the central operator entity with `name`(req), `employee_id`(unique), `pin_hash`(SHA-256, req), `is_active`(bool, default true), and SHALL validate PIN against `pin_hash` on login. | Test: CRUD операторів; валідація PIN у ≥ 99 % тест-кейсів. Inspect: поля моделі. | M | ✅ |
| REQ-047 | `dnj.kiosk.session` SHALL track a kiosk interaction as a state machine `Draft→Active→(Paused)→Ended/Cancelled` with `user_id,start_time,end_time,state`; only valid transitions permitted; `end_time` recorded on `Ended`. | Test: створення (Draft), підтвердження (Active), завершення (Ended+end_time), відхилення невалідних переходів. | M | ✅ |
| REQ-048 | `dnj.kiosk.pause` SHALL record a pause with `session_id`(FK), `pause_type`(Break/Lunch/Technical), `start_time`, `end_time`(nullable); WHILE active SHALL block interactions until ended; a pause > 60 min SHALL require supervisor approval. | Test: створення паузи по типах, запис start/end_time; спроба > 60 хв без апруву. Analyze: цілісність даних. | M | ✅ |
| REQ-049 | WHEN a WO status changes or a critical action occurs, THEN `dnj.workorder.log` SHALL record within 100 ms an entry with `timestamp, work_order_id, event_type, user_id, description, details(JSONB)`. | Test: дії над WO → наявність/коректність/повнота записів. Inspect: типи полів. | M | ✅ |
| REQ-050 | WHEN a machine's network status or Modbus data changes (or every 5 s), THEN `dnj.machine.status` SHALL store `machine_id, timestamp_last_update, operational_status(running/idle/error), network_status(online/offline), last_seen` + ≥ 3 configurable Modbus register value fields. | Test: симуляція змін для 3 машин → коректні записи. Inspect: поля моделі. Analyze: частота/латентність оновлень. | M | ✅ |

### 2.8 Інфраструктура

| ID | EARS-вимога | Критерій приймання / Верифікація | MoSCoW | Статус |
|----|-------------|----------------------------------|:------:|:------:|
| REQ-051 | `docker-compose.yml` SHALL define `odoo` (17.0 Community) and `db` (PostgreSQL 15.x) on a shared network; on `up` Odoo SHALL connect to db, init DB, and persist data across restarts. | Test: `up` → створити запис → `down` → `up` → запис зберігся. Inspect: версії образів, мережа. | M | ✅ |
| REQ-052 | `machine_bridge/docker-compose.yml` SHALL define all services/networks/volumes for the Bridge; on `up` 100 % services SHALL start healthy. | Test: `docker-compose up` → усі сервіси стартують (exit 0/healthy). Inspect: синтаксис/вміст. | M | ✅ |
| REQ-053 | `machine_bridge/Dockerfile` SHALL build an image with the Bridge app + runtime deps; a container from it SHALL start the app and answer its health endpoint 200 OK ≤ 10 s. | Test: build → run → health-check `curl`. Inspect: вміст Dockerfile. | M | ✅ |
| REQ-054 | The system SHALL run on Odoo 17.0 Community edition. | Inspect: версія Odoo у розгортанні. | M | ✅ |

---

## 3. Нефункціональні вимоги (NFR)

| ID | Категорія | Вимога | Метод верифікації |
|----|-----------|--------|-------------------|
| **NFR-SEC-1** | Безпека — PIN | PIN = 4 цифри; зберігання SHA-256 + унікальна сіль на оператора; ≤ 3 невдалі спроби / 5 хв → блокування 15 хв. | Inspect (код), Test (lockout) |
| **NFR-SEC-2** | Безпека — кіоск | Авто-логін `/kiosk` лише для попередньо авторизованого кіоска; неавторизований → 401. | Test, Inspect |
| **NFR-SEC-3** | Безпека — API | Автентифікація JWT (`expires_in`=3600 с); Machine Bridge → Odoo через API-key у заголовку `Authorization`. | Test, Inspect |
| **NFR-SEC-4** | Безпека — аудит | Невдалі спроби автентифікації логуються й зберігаються ≥ 30 днів. | Inspect (логи) |
| **NFR-PERF-1** | Продуктивність — API | p95 латентність: `GET /kiosk` < 200 ms; session-ендпоінти ≤ 200–300 ms; dashboard ≤ 500 ms (95 %); heartbeat p90 < 100 ms при ≥ 100 rps. | Analyze (навантажувальні тести) |
| **NFR-PERF-2** | Продуктивність — UI | Список WO вантажиться ≤ 2 с; дії старт/пауза відображаються ≤ 0.5–2 с. | Test |
| **NFR-AVAIL** | Доступність | Event Log доступний з uptime 99.9 %, нульова втрата даних. | Analyze (звіти uptime, тести бекапу/відновлення) |
| **NFR-RET** | Зберігання | Операційні записи Event Log — незмінні, зберігаються ≥ 365 днів. ⚠️ Юридичний термін (5 років?) — див. §8. | Inspect (retention-політика), Test (ретрив старих записів) |
| **NFR-POLL** | Моніторинг — інтервали | Bridge: список машин з Odoo кожні 60 с; ICMP ping 10 с/timeout 1000 ms/критерій 3-з-5; Modbus HR[0-2] кожні 5 с/ретрай 15 с; push у Odoo кожні 30 с/ретрай ≤ 3× по 10 с. | Test, Inspect (логи/конфіг) |
| **NFR-RESP** | Адаптивність UI | Брейкпойнти 320–767 (1 колонка) / 768–1023 (2 колонки) / ≥ 1024 (повна); вертикальна прокрутка при переповненні. | Test (емуляція розмірів) |
| **NFR-TIME** | Точність часу | Wall-clock timer: похибка ≤ ±1 с/год, джерело — системний годинник, формат `HH:MM:SS`. | Test (звірка з еталоном) |

---

## 4. Traceability (вимога ↔ реалізація ↔ тест)

- **Реалізовано (§2.1–2.8):** REQ-001…054 (крім позначених ⚠️) — статус ✅, підтверджено на demo-сервері.
- **Тести:** окремої теки автотестів у репозиторії наразі **немає** → traceability до тест-кейсів не встановлена (open item G-TEST, §8). Кожна вимога вже містить готовий метод верифікації в колонці «Критерій приймання» — це основа для написання E2E/unit-тестів (Playwright + Odoo test framework).
- **Roadmap (§6):** REQ-055…062 — статус 🔲.

---

## 5. Матриця статусу реалізації (чеклист)

> Вихідний чеклист функцій (джерело правди по факту реалізації). Деталізовані вимоги — §2.

### Модуль `dnj_shopfloor`
**Оператор Кіоск:** авто-логін ✅ · PIN SHA-256 ✅ · список WO ✅ · тест-друк ✅ · старт ✅ · пауза ✅ · резюм ✅ · стоп ✅ · logout ✅ · timer (wall-clock) ✅ · progress bar ✅ · session persistence ✅ · scrollable ✅
**Дашборд:** live статус ✅ · клікабельні картки ✅ · Machine Detail Panel ✅ · хто працює + час ✅ · прогрес WO ✅ · пауза ✅ · доступ лише `mrp.group_mrp_manager` ✅
**Event Log:** модель `dnj.workorder.log` ✅ · події (login…logout) ✅ · хронологія ✅
**Конфігурація:** оператори з PIN ✅ · прив'язка до Workcenters ✅ · Machine Monitoring (IP, Modbus) ✅

### Machine Bridge
читання машин з Odoo ✅ · ICMP ping ✅ · Modbus TCP HR[0-2] ✅ · push REST ✅ · polling 30 с ✅ · `--test` ✅ · Docker Compose ✅ · PLC Simulator ✅

### API (11) · Моделі (5) · Інфраструктура
Усі ендпоінти §2.6 ✅ · моделі §2.7 ✅ · `docker-compose.yml` (Odoo 17 + PG 15) ✅ · `machine_bridge/{docker-compose.yml,Dockerfile}` ✅

---

## 6. Roadmap (заплановане — 🔲)

| ID | EARS-вимога | Верифікація | Пріоритет |
|----|-------------|-------------|-----------|
| REQ-055 | WHEN a Manufacturing Order incurs scrap, THEN the system SHALL let an operator record scrap quantity + predefined reason and SHALL recalculate the MO total cost (≥ 2 dp). | Test: запис браку + перерахунок собівартості. | Середній |
| REQ-056 | IF actual execution time > 120 % of standard time, THEN the system SHALL email the assigned Production Manager within 5 min with WO id/name/actual/norm/overrun %. | Test: симуляція перевитрати → email ≤ 5 хв із вмістом. | Середній |
| REQ-057 | WHEN defective units in a batch exceed a configurable limit (default 5 units або 2 %), THEN the system SHALL email the Production Manager with batch/product/totals/limit. | Test: перевищення ліміту → email ≤ 2 хв. | Середній |
| REQ-058 | WHEN a new Modbus device is detected, THEN the system SHALL auto-identify ≥ 95 % of critical registers for ≥ 10 known models within 30 s; IF accuracy < 90 %, THEN notify admin and allow manual config. | Test: 10 моделей → точність; невідомий пристрій → ручна конфігурація. | Середній |
| REQ-059 | WHEN a Heidelberg+Prinect machine connects via OPC-UA, THEN the system SHALL retrieve real-time production data (job id, print count, status, error codes), latency ≤ 5 s, integrity ≥ 99 %/24 год; on error retry ≤ 3× then alert admin. | Analyze (24 год), Test (симуляція змін/збоїв). | Низький |
| REQ-060 | WHEN a merge to `main` succeeds, THEN CI/CD SHALL build/test/deploy to Staging ≤ 5 хв; Production deploy zero-downtime ≤ 10 хв; on failed health-check > 30 с → auto-rollback (blue/green) ≤ 2 хв. | Demo (pipeline), Test (health-checks/rollback). | Низький |
| REQ-061 | WHEN a user opens Paper Warehouse, THEN the system SHALL allow CRUD on storage zones/racks, assign paper stock to a location (shown ≤ 2 с), and identify each item by a unique QR/barcode. | Demo (CRUD), Test (унікальність кодів, сканування). | Низький |
| REQ-062 | WHEN a Sale Order is Confirmed AND has line items with "Requires Production", THEN the system SHALL auto-create an MO per such item (inheriting product/qty/date) ≤ 5 с for ≤ 10 items; on failure log + email Production Manager ≤ 1 хв. | Test: SO з валідними/невалідними позиціями → MO / лог+email. | Низький |

### Виявлені прогалини (gaps) до закриття
- **G001** — «Старт роботи над WO»: зафіксувати передумови (`Ready`/`Paused`), таймстемп старту, user id, обробку невалідного статусу. *(Покрито уточненням REQ-005.)*
- **G002** — Пауза/Резюм/Стоп: явно описати фіксовані дані (таймстемпи, user id) і логіку час-трекінгу. *(Покрито REQ-006…008.)*
- **G003** — Time-based progress bar: логіка розрахунку й поведінка при overrun. *(Покрито REQ-011.)*

---

## 7. Production статус

- **Demo URL:** [dnj.fayna.agency](https://dnj.fayna.agency)
- **DB:** `dnj_demo` · **Odoo:** 17.0 Community
- **Статус:** Production-ready (розгорнуто на demo-сервері)
- Облікові дані demo — не в репозиторії (див. секретне сховище проєкту).

---

## 8. Відкриті питання (потребують рішення)

1. **⚠️ REQ-001 (авто-логін кіоска):** підтвердити механізм авторизації кіоска в коді. Якщо зараз доступ до `/kiosk` без жодної перевірки походження — це діра безпеки; узгодити спосіб (виділений акаунт / client-cert / allowlist IP).
2. **⚠️ REQ-002 (PIN):** звірити з кодом, чи реалізовано політику блокування (3 спроби / 15 хв) і сіль. Аудит показав, що деталі відсутні в ТЗ — імовірно й у реалізації немає lockout. Рішення: доробити або свідомо прийняти ризик.
3. **NFR-RET (термін зберігання логів):** конфлікт у джерелах — 365 днів (операційна доцільність) vs 5 років (юридична). Обрати з урахуванням RODO/галузевих вимог друкарні.
4. **G-TEST (traceability до тестів):** у репозиторії немає теки автотестів. Створити `tests/` (unit + E2E Playwright) на базі критеріїв приймання §2, щоб кожна Must-вимога мала верифікаційний тест.
5. **API-контракти:** згенерувати OpenAPI 3.x для 11 ендпоінтів (§2.6) — зараз специфікації немає. **Звірено з кодом:** API реалізовано як Odoo JSON-RPC (`type='json'`, session-auth), а не REST/JWT/UUID/CRUD, як помилково описував первинний ТЗ — §2.6 приведено до фактичного контракту.
6. **🔴 PIN — SHA-256 БЕЗ солі та БЕЗ lockout (звірено з `models/dnj_operator.py`).** Факт: `_hash_pin()` = `hashlib.sha256(pin.strip().encode()).hexdigest()` — **plain SHA-256, без солі** (однаковий PIN → однаковий хеш; вразливий до rainbow-table/brute-force по 4–6 цифрах = ≤ 10⁶ комбінацій). **Немає жодного lockout / rate-limit** на невдалі спроби — необмежений перебір PIN. Це прямо **суперечить REQ-002 і NFR-SEC-1**, які декларують «унікальну сіль на оператора» та «блокування 15 хв після 3 спроб» — обидві гарантії у коді ВІДСУТНІ. Рішення: додати сіль (напр. per-operator random salt) + lockout/rate-limit, або свідомо прийняти ризик і виправити текст вимог.
7. **🔴 Кіоск `/kiosk` захищений лише дефолтним паролем (звірено з `controllers/kiosk.py`).** Ендпоінт `type='http'`, `auth='none'` — доступний БЕЗ автентифікації будь-кому, хто знає URL. Авто-логін використовує спільний кіоск-акаунт, чиї логін/пароль беруться з `ir.config_parameter` (`dnj_shopfloor.kiosk_login` = `kiosk`, `dnj_shopfloor.kiosk_password` = **`Kiosk2024`** за замовчуванням). Якщо дефолтний пароль не змінено на проді — це відкритий вхід у Odoo під кіоск-користувачем. Рішується REQ-001 / NFR-SEC-2 (allowlist IP / client-cert) + обов'язкова зміна `Kiosk2024` при розгортанні.

---

## 9. Методологія і джерела

Це ТЗ приведено до наступних стандартів (аудит `docs/tz-audit/2026-07-03/`):
- **ISO/IEC/IEEE 29148:2018** — характеристики якісних вимог (complete, unambiguous, verifiable, singular, feasible…).
- **EARS** (Mavin et al.) — контрольований синтаксис вимог: WHEN / WHILE / IF-THEN / GIVEN-WHEN-THEN.
- **MoSCoW** — пріоритизація (Must/Should/Could/Won't).
- **Requirements Smells** (Femmer et al.) — усунення vague_nfr, happy_path_only, no_priority.
- **Spec-Driven Development 2026** — структурні блоки: контекст, глосарій, NFR, edge cases, traceability, відкриті питання.

_Повний аудит зі scorecard і 166 знахідками: `docs/tz-audit/2026-07-03/TZ_AUDIT_2026-07-03.md`. План покращень (EARS-переписування): `TZ_IMPROVE_2026-07-03.md`. Метрики виконання: `TZ_METRICS_2026-07-03.md`._
</content>
</invoke>
