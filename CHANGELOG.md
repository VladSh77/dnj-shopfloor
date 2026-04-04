# CHANGELOG — dnj-shopfloor

Формат: `## [date] — YYYY-MM-DD`

---

## [2026-04-03]

- Docs: professional badges — Odoo, Python, OWL, Modbus TCP, Docker, Status, demo link

## [2026-03-25]

- Docs: оновлено README і TECHNICAL.md — machine detail panel, timer fix, session fix
- Fix: robust timer через `workStartTs + tick` — коректний час після refresh
- Fix: закриття всіх сесій на машині при новому login

## [2026-03-24]

- Feat: machine detail panel — кліком на картку → повна статистика машини
- Feat: таймер не зупиняється під час паузи — відстежує wall-clock production time
- Docs: повний README + оновлений TECHNICAL.md
- Fix: `attrs=` → `invisible=` для Odoo 17 сумісності
- Fix: `action_dnj_machine_status` переміщено перед menuitem reference
- Feat: Machine Monitoring конфіг через Odoo UI + Modbus TCP bridge
- Fix: machine bridge db name `dnj_demo`
- Fix: кіоск-екрани scrollable на маленьких телефонах/планшетах
- Feat: machine bridge — network ping status per workcenter
- Fix: `web_icon` для root menu (app switcher)
- Feat: module icon (DNJ logo)
- Fix: time bar 44px, завжди видима
- Feat: time-based progress bar у кіоску і дашборді
- Fix: dashboard menu — тільки для `mrp.group_mrp_manager`
- Fix: dashboard menuitem → `kiosk_views.xml` (load order)
- Fix: повний XMLID для dashboard menu action reference
- Feat: manager dashboard, auto-login `/kiosk`, timer persistence, docs
