# ТЗ — dnj-shopfloor (Odoo 17 Shop Floor Module)

> Повний чеклист реалізованих та запланованих функцій.
> ✅ — готово | 🔲 — заплановано | ❌ — скасовано

---

## 1. Модуль `dnj_shopfloor` (Odoo addon)

### Оператор Кіоск

| Функція | Статус |
|---------|--------|
| Авто-логін (`GET /kiosk`) — кіоск-акаунт без пароля | ✅ |
| PIN аутентифікація оператора (SHA-256 hash) | ✅ |
| Список Work Orders для машини | ✅ |
| Тест-друк | ✅ |
| Старт роботи над WO | ✅ |
| Пауза | ✅ |
| Резюм після паузи | ✅ |
| Стоп | ✅ |
| Logout | ✅ |
| Timer (wall-clock, не інкрементний) | ✅ |
| Time-based progress bar | ✅ |
| Session persistence (відновлення після refresh) | ✅ |
| Scrollable на планшетах / малих екранах | ✅ |

### Менеджерський Дашборд

| Функція | Статус |
|---------|--------|
| Live статус всіх машин | ✅ |
| Клікабельні картки машин | ✅ |
| Machine Detail Panel — статистика машини | ✅ |
| Хто зараз працює + скільки часу | ✅ |
| Прогрес WO | ✅ |
| Пауза на дашборді | ✅ |
| Обмеження доступу: тільки `mrp.group_mrp_manager` | ✅ |

### Event Log

| Функція | Статус |
|---------|--------|
| Модель `dnj.workorder.log` | ✅ |
| Події: login, test_print, start, pause, resume, stop, logout | ✅ |
| Повна хронологія подій | ✅ |

### Конфігурація

| Функція | Статус |
|---------|--------|
| Оператори з PIN — `DNJ Shopfloor → Configuration → Operators` | ✅ |
| Прив'язка операторів до машин (Workcenters) | ✅ |
| Machine Monitoring конфіг через Odoo UI (IP, Modbus) | ✅ |

---

## 2. Machine Bridge (`machine_bridge/`)

| Функція | Статус |
|---------|--------|
| Читання списку машин та їх IP з Odoo | ✅ |
| ICMP ping per machine (online/offline) | ✅ |
| Modbus TCP читання `HR[0-2]` (статус, швидкість, лічильник) | ✅ |
| Push результатів в Odoo через REST | ✅ |
| Polling кожні 30 секунд (continuous mode) | ✅ |
| `--test` режим (один цикл і вихід) | ✅ |
| Docker Compose deployment | ✅ |
| PLC Simulator для тестів (з demo-industrial-iot) | ✅ |

---

## 3. API ендпоінти (11 штук)

| Ендпоінт | Статус |
|---------|--------|
| `GET /kiosk` | ✅ |
| `POST /dnj_shopfloor/authenticate` | ✅ |
| `POST /dnj_shopfloor/session/open` | ✅ |
| `POST /dnj_shopfloor/session/action` | ✅ |
| `POST /dnj_shopfloor/session/status` | ✅ |
| `POST /dnj_shopfloor/workorders` | ✅ |
| `POST /dnj_shopfloor/workcenters` | ✅ |
| `POST /dnj_shopfloor/dashboard` | ✅ |
| `POST /dnj_shopfloor/machine/config` | ✅ |
| `POST /dnj_shopfloor/machine/heartbeat` | ✅ |
| `POST /dnj_shopfloor/machine/stats` | ✅ |

---

## 4. Моделі Odoo

| Модель | Статус |
|--------|--------|
| `dnj.operator` — оператор + PIN (SHA-256) | ✅ |
| `dnj.kiosk.session` — сесія (state machine) | ✅ |
| `dnj.kiosk.pause` — пауза | ✅ |
| `dnj.workorder.log` — Event Log | ✅ |
| `dnj.machine.status` — мережевий моніторинг + Modbus | ✅ |

---

## 5. Інфраструктура

| Компонент | Статус |
|-----------|--------|
| `docker-compose.yml` — Odoo + PostgreSQL 15 | ✅ |
| `machine_bridge/docker-compose.yml` | ✅ |
| `machine_bridge/Dockerfile` | ✅ |
| Odoo 17.0 Community | ✅ |

---

## 6. Roadmap

| Функція | Статус | Пріоритет |
|---------|--------|-----------|
| Scrap — вплив на собівартість MO | 🔲 | Середній |
| Алерти менеджеру (час > 120% норми) | 🔲 | Середній |
| Алерти менеджеру (брак > ліміту) | 🔲 | Середній |
| Автовизначення Modbus регістрів per машина | 🔲 | Середній |
| OPC-UA для нових Heidelberg з Prinect | 🔲 | Низький |
| CI/CD (GitHub Actions → auto deploy) | 🔲 | Низький |
| Фаза 3: Склад паперу (зони, стелажі, QR/штрихкод) | 🔲 | Низький |
| Фаза 4: Sale Order → auto MO | 🔲 | Низький |

---

## Production статус

- **Demo URL:** [dnj.fayna.agency](https://dnj.fayna.agency)
- **Login:** `manager` / `Manager2024!`
- **DB:** `dnj_demo`
- **Статус:** Production-ready (deployed on demo server)
