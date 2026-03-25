# DNJ Shop Floor — Odoo 17 Module

**Кіоск для операторів друкарні + менеджерський дашборд + міст до промислових машин**

Автор: [Fayna Digital](https://fayna.agency)
Клієнт: Drukarnia DNJ, Jarocin, Польща
Odoo: 17.0 Community
Демо: [https://dnj.fayna.agency](https://dnj.fayna.agency) (login: `manager` / `Manager2024!`)

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

Автологін як `kiosk`, перенаправляє на кіоск.

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
cd Fayna-Projects/demo-industrial-iot
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

Всі ендпоінти: `POST`, `Content-Type: application/json`, `auth='user'`.

| URL | Призначення |
|---|---|
| `GET /kiosk` | Авто-вхід планшету |
| `POST /dnj_shopfloor/authenticate` | Перевірка PIN оператора |
| `POST /dnj_shopfloor/session/open` | Відкрити сесію (закриває всі попередні сесії на машині) |
| `POST /dnj_shopfloor/session/action` | Дії: start, pause, resume, stop, logout |
| `POST /dnj_shopfloor/session/status` | Поточний стан сесії |
| `POST /dnj_shopfloor/workorders` | Список Work Orders для машини |
| `POST /dnj_shopfloor/workcenters` | Список усіх активних машин |
| `POST /dnj_shopfloor/dashboard` | Живий статус всіх машин (для дашборду) |
| `POST /dnj_shopfloor/machine/config` | Список машин з IP для bridge |
| `POST /dnj_shopfloor/machine/heartbeat` | Bridge надсилає результати пінгів |
| `POST /dnj_shopfloor/machine/stats` | Детальна статистика машини (для панелі деталей) |

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
