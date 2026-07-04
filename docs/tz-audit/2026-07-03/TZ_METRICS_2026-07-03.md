# Метрики ефективності реалізації ТЗ — /Users/kobzar/Developer/Fayna-Workspace/Projects/dnj-shopfloor/docs/TZ.md

_Дата: 2026-07-03. Як міряти виконання ТЗ у ході розробки; базлайн з цього аудиту. Повторний прогін для трендів:_
`python3 ~/.claude/skills/tz-audit/scripts/tz_audit_loop.py /Users/kobzar/Developer/Fayna-Workspace/Projects/dnj-shopfloor/docs/TZ.md --tests <тека>`

| Метрика | Формула | Джерело даних | Частота | Поріг/базлайн |
|---|---|---|---|---|
| Traceability coverage | % вимог зі зматченим тестом | цей луп / CI-скрипт map req↔test | на кожен реліз | зараз: н/д%; ціль 100% критичних, ≥70% всіх |
| Orphans | вимоги без тесту + тести без вимоги | цей луп (фаза trace) | на кожен реліз | зараз: 0+0; ціль 0 |
| Verification-method coverage | % вимог із зазначеним методом | фаза per-req цього лупа | щоміс | зараз: 5%; ціль 100% |
| Вимірність | % вимог із числами/порогами | фаза per-req | щоміс | зараз: 6%; ціль ≥90% |
| Spec-drift | нові розбіжності код↔ТЗ між прогонами | порівняння scorecard/знахідок двох прогонів лупа | на реліз | 0 нових |
| Smell density | smells на 100 вимог | фаза per-req | щоміс | тренд ↓ |
| DoD-виконання | % закритих вимог з доказом (CI-run/лог/скрін) | PR-рев'ю + статуси в ТЗ | щотижня | 100% закритих |

## Базлайн scorecard (2026-07-03)
| Характеристика | Оцінка (0-2) |
|---|---|
| appropriate | 1.9 |
| complete | 0.18 |
| conforming | 1.74 |
| correct | 1.76 |
| feasible | 1.97 |
| necessary | 1.68 |
| singular | 1.87 |
| unambiguous | 0.66 |
| verifiable | 0.35 |

| Метрика | % |
|---|---|
| verification-method coverage | 5 |
| вимірність (числа/пороги) | 6 |
| EARS-parsable | 19 |

## Джерела (цитувати у звіті)
- ISO/IEC/IEEE 29148:2018 — Systems and software engineering — Requirements engineering. Шаблон/огляд: https://www.well-architected-guide.com/documents/iso-iec-ieee-29148-template/ ; https://www.cwnp.com/req-eng/
- EARS (Easy Approach to Requirements Syntax), Mavin et al. — шаблони WHEN/WHILE/IF-THEN/WHERE.
- Spec-Driven Development: From Code to Contract in the Age of AI Coding Assistants — https://arxiv.org/html/2602.00180v1
- Spec-Driven Development: The Definitive 2026 Guide — https://thebcms.com/blog/spec-driven-development
- How To Write Clear, Measurable Software Requirements in 2026 — https://www.designrush.com/agency/software-development/trends/software-requirements-specification
- Requirements Smells (Femmer et al.) — https://arxiv.org/pdf/1611.08847
- Well-Formed Quality of System Requirements for ISO 29148-2018 (NLP metric) — https://www.researchgate.net/publication/385802396
- QUARE: Quality-Aware Requirements Analysis through Multi-Agent Dialectical Negotiation — https://arxiv.org/pdf/2603.11890
