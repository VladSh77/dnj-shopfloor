# 🏭 DNJ Shop Floor Kiosk for Odoo 17

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Modbus](https://img.shields.io/badge/Modbus-TCP%20Bridge-red)
![License](https://img.shields.io/badge/License-LGPL--3.0-green.svg)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

**Developed by [Fayna Digital](https://fayna.agency) for DNJ — Author: Volodymyr Shevchenko**

---

**Кіоск для операторів друкарні + менеджерський дашборд + міст до промислових машин**

---

## Що зроблено

### Модуль `dnj_shopfloor`

| Функція | Опис |
|---|---|
| **Кіоск для оператора** | Планшет на виробничій лінії. PIN-вхід, черга Work Orders, тест-друк, таймер, пауза, стоп |
| **Менеджерський дашборд** | Живий статус усіх машин: хто працює, скільки часу, прогрес, пауза. Клікабельні картки машин |
| **Деталі машини** | Статистика за сьогодні, тижневі оператори, остання 10 сесій, статус Modbus, заглушки паперу/фарби |
| **Моніторинг машин** | Ping-статус (online/offline) кожної машини + Modbus TCP (швидкість, лічильник) |
| **Event Log** | Повна хронологія подій: login, test_print, start, pause, resume, stop, logout |
| **Session persistence** | Кіоск відновлює сесію після перезавантаження сторінки/планшету |

### Machine Bridge (`machine_bridge/`)

Окремий Docker-сервіс. Кожні 30 с:
1. Читає список машин та їх IP з Odoo (конфігурується через UI)
2. ICMP-пінгує кожну машину
3. Якщо увімкнено Modbus TCP — читає регістри (статус, швидкість, лічильник)
4. Надсилає результати в Odoo через REST

---

## Структура репозиторію

```
dnj-shopfloor/
├── addons/dnj_shopfloor/          # Odoo модуль
│   ├── models/
│   │   ├── dnj_operator.py        # Оператор + PIN (SHA-256)
│   │   ├── dnj_kiosk_session.py   # Сесія (стан-машина)
│   │   ├── dnj_kiosk_pause.py     # Пауза
│   │   ├── dnj_workorder_log.py   # Event Log
│   │   └── dnj_machine_status.py  # Моніторинг мережі + Modbus
│   ├── controllers/
│   │   └── kiosk.py               # 11 JSON-RPC ендпоінтів
│   ├── views/
│   │   ├── kiosk_views.xml        # Кіоск + дашборд actions
│   │   └── dnj_operator_views.xml # Оператори, сесії, логи, Machine Monitoring
│   ├── static/src/
│   │   ├── js/kiosk_app.js        # OWL кіоск
│   │   ├── js/dashboard_app.js    # OWL дашборд
│   │   └── xml/                   # Шаблони
│   └── security/
│       └── ir.model.access.csv
├── machine_bridge/                 # Bridge сервіс
│   ├── bridge.py                  # Головний скрипт
│   ├── config.py                  # Odoo credentials + timing
│   ├── Dockerfile
│   └── docker-compose.yml
└── docker-compose.yml             # Odoo + PostgreSQL
```

---

## Швидкий старт

### 1. Вимоги
- Docker + Docker Compose
- Odoo 17.0 Community
- PostgreSQL 15

### 2. Встановлення модуля

```bash
git clone https://github.com/VladSh77/dnj-shopfloor.git
cd dnj-shopfloor

# Запустити Odoo
docker compose up -d

# Встановити модуль (після першого запуску)
docker compose run --rm web odoo -i dnj_shopfloor -d <db_name> --stop-after-init
docker compose restart web
```

### 3. Перший вхід (кіоск)

Відкрити на планшеті: `http://<server>/kiosk`

Автологін як спільний користувач `kiosk`, перенаправляє на кіоск.

> ⚠️ **Безпека:** `/kiosk` — це `GET`, `auth='none'` (без пароля користувача). Авто-логін бере логін/пароль зі `ir.config_parameter`:
> - `dnj_shopfloor.kiosk_login` (дефолт `kiosk`)
> - `dnj_shopfloor.kiosk_password` (дефолт **`Kiosk2024`**)
>
> **Обов'язково змініть `Kiosk2024` при розгортанні на прод** — інакше будь-хто, хто знає URL, увійде в Odoo під кіоск-акаунтом.

### 4. Дашборд для менеджера

`DNJ Shopfloor → Dashboard` (доступно тільки для групи `MRP Manager`)

---

## Налаштування операторів

**Odoo → DNJ Shopfloor → Configuration → Operators → New**

| Поле | Значення |
|---|---|
| Name | Ім'я оператора |
| PIN | Встановити через форму (зберігається як SHA-256) |
| Workcenters | Машини, до яких має доступ |

PIN за замовчуванням для тестових операторів: **1234**

---

## Підключення машини до моніторингу

### Крок 1 — Налаштування в Odoo

**DNJ Shopfloor → Configuration → Machine Monitoring → New**

| Поле | Що вводити |
|---|---|
| Machine | Вибрати workcenter |
| IP Address | `192.168.1.100` — IP машини в заводській мережі |
| Modbus TCP | ☑ якщо машина підтримує Modbus (більшість промислових) |
| Modbus Port | `502` (стандарт для промислових машин) |
| Notes | Модель, контакт сервісника, карта регістрів |

### Крок 2 — Перевірка мережевого з'єднання

```bash
# З мережі де стоїть сервер:
ping 192.168.1.100

# Якщо ping не проходить — перевірити firewall, VLAN
```

### Крок 3 — Перевірка Modbus (опціонально)

```bash
# Запустити симулятор (для тестів без реальної машини):
cd ../demo-industrial-iot   # сусідній репозиторій поруч із dnj-shopfloor
python plc_simulator.py    # Modbus сервер на 127.0.0.1:5020

# Відкрити Odoo, вказати IP=127.0.0.1, Port=5020, Modbus=☑
```

### Крок 4 — Запуск Machine Bridge

```bash
cd machine_bridge

# Тест підключення до Odoo (показує список машин і виходить):
python bridge.py --test

# Один раунд пінгів:
python bridge.py

# Безперервний режим (кожні 30 с):
python bridge.py --loop

# Docker (production):
docker compose up -d --build
```

### Карта Modbus регістрів (стандартна)

| Регістр | Значення |
|---|---|
| `HR[0]` | Статус: `0` = стоїть, `1` = працює |
| `HR[1]` | Швидкість (аркушів/год) |
| `HR[2]` | Лічильник (загальна кількість аркушів) |

> Для конкретної моделі машини уточніть у документації або у сервісного інженера. Карту регістрів можна змінити в `bridge.py` → `ModbusClient.read_machine_state()`.

---

## Деплой на сервер

```bash
# 1. Запуш зміни
git push

# 2. На сервері — тільки JS/XML зміни (без нових моделей):
git pull
docker compose restart web
# + hard-refresh у браузері (Ctrl+Shift+R)

# 3. На сервері — зміни моделей або XML views:
git pull
docker compose stop web
docker compose run --rm web odoo -u dnj_shopfloor -d dnj_demo --stop-after-init -r odoo -w odoo_secret_password
docker compose start web

# 4. Перебудова Machine Bridge (після змін bridge.py або config.py):
cd machine_bridge
docker compose up -d --build
```

---

## API ендпоінти

Це **Odoo JSON-RPC** (`type='json'`), а не «чистий REST»: відповідь завжди `200 OK` з обгорткою `{"result": …}`, а прикладні помилки повертаються в `result` як `{"success": false, "error": …}`. Ідентифікатори — цілі id Odoo (не UUID), автентифікація — сесія Odoo (cookie `session_id`), не JWT.

**Виняток:** `GET /kiosk` — це `type='http'`, `auth='none'`, метод `GET` (авто-логін планшету без пароля користувача). Решта ендпоінтів нижче — `POST`, `Content-Type: application/json`, `auth='user'` (потрібна активна сесія Odoo).

| URL | Метод / auth | Призначення |
|---|---|---|
| `/kiosk` | `GET`, `auth='none'` | Авто-вхід планшету (дефолтний пароль `Kiosk2024`, див. вище) |
| `/dnj_shopfloor/authenticate` | `POST`, `auth='user'` | Перевірка PIN оператора (повертає `operator_id`+`name`, не токен) |
| `/dnj_shopfloor/session/open` | `POST`, `auth='user'` | Відкрити сесію (закриває всі попередні сесії на машині) |
| `/dnj_shopfloor/session/action` | `POST`, `auth='user'` | Дії: test_print, confirm_machine, select_workorder, start_work, pause, resume, stop, logout |
| `/dnj_shopfloor/session/status` | `POST`, `auth='user'` | Поточний стан сесії (read-only полінг) |
| `/dnj_shopfloor/workorders` | `POST`, `auth='user'` | Список Work Orders для машини (read-only) |
| `/dnj_shopfloor/workcenters` | `POST`, `auth='user'` | Список усіх активних машин (read-only) |
| `/dnj_shopfloor/dashboard` | `POST`, `auth='user'` | Живий статус всіх машин (для дашборду) |
| `/dnj_shopfloor/machine/config` | `POST`, `auth='user'` | Список машин з IP для bridge (read-only) |
| `/dnj_shopfloor/machine/heartbeat` | `POST`, `auth='user'` | Bridge надсилає результати пінгів |
| `/dnj_shopfloor/machine/stats` | `POST`, `auth='user'` | Детальна статистика машини (read-only, для панелі деталей) |

Детально: [addons/dnj_shopfloor/TECHNICAL.md](addons/dnj_shopfloor/TECHNICAL.md)

---

## Відомі обмеження / наступні кроки

- [ ] Scrap → вплив на собівартість MO
- [ ] Алерти менеджеру (час > 120% норми, брак > ліміту)
- [ ] Автоматичне визначення Modbus регістрів per машина (зараз фіксована карта HR[0-2])
- [ ] OPC-UA для нових Heidelberg з Prinect
- [ ] CI/CD (GitHub Actions → auto deploy)
- [ ] Фаза 3: Склад паперу (зони, стелажі, QR/штрихкод)
- [ ] Фаза 4: Продаж → виробництво (Sale Order → auto MO)
