# Sales Manager FIRST — Catalog Config Resolver

Компонент SFA-P38B-DEV-R1 читает уже принятый каталог и передаёт только `raw_config` в существующий вызов F128 `resolve_campaign_projection`. Это read-only шов. Он не выбирает текущую версию каталога, не кэширует чтение и не выдаёт право на отправку.

Техническая ревизия R1. Редакция передачи H2-AUDIT-FIX1. Граница готовности: `CATALOG_TO_F128_COMPONENT_ONLY`.

## Как устроен возврат

- `06_Dmitriev.zip` — исходный выданный архив, SHA-256 `e6208caa91704c67b052f65681f0b59df54aaf5adf4af79fc67c54fddb382a7d`.
- `06_Dmitriev/SFA-P38B-DEV-R1/` — тот же комплект плюс разрешённые файлы реализации.
- `SFA-P38B-DEV-R1-return.zip` — собранный возврат, SHA-256 `684fee7fa17130c7ec4b364c01a0a092b8e069e56cd2faec527ae591745eb793`.
- Реализация: `06_Dmitriev/SFA-P38B-DEV-R1/source/first_materials_integration/catalog_config.py`.
- Отчёт, ограничения и предложение подключения: `06_Dmitriev/SFA-P38B-DEV-R1/raw_logs/RETURN_REPORT.md`.

## Запуск проверок

Из каталога `06_Dmitriev/SFA-P38B-DEV-R1`:

```
python -B RUN_CHECKS.py integrity
python -B RUN_CHECKS.py baseline
python -B RUN_CHECKS.py acceptance
python -B RUN_CHECKS.py candidate
```

Фактическая среда этих запусков: Python 3.12.8, Windows-11-10.0.26300-SP0.

## Фактические результаты

До реализации, на неизменённом ZIP: integrity PASS, baseline PASS (186 тестов), acceptance `MISSING_IMPLEMENTATION` exit 3, candidate `MISSING_CANDIDATE_TESTS` exit 4.

После реализации, в двух отдельных чистых копиях:

| Проверка | Прогон 1 | Прогон 2 |
| --- | --- | --- |
| integrity | PASS, exit 0 | PASS, exit 0 |
| baseline | PASS, 186, exit 0 | PASS, 186, exit 0 |
| acceptance | PASS, 13, exit 0 | PASS, 13, exit 0 |
| candidate | PASS, 22, exit 0 | PASS, 22, exit 0 |
| integrity после тестов | PASS, exit 0 | PASS, exit 0 |

Пропусков не было. Все 90 защищённых файлов совпали с манифестом.

## Границы

Готово только компонентное офлайн-чтение каталога для callback F128. `release_mode` остаётся `NO_OUTBOUND`.

Не выполнено и не заявляется готовым:

- macOS — NOT_RUN;
- PostgreSQL — NOT_RUN;
- installed/connected приёмка — NOT_RUN;
- SQL, production-установка, credentials, реальные отправки — не выполнялись;
- исторические B8 CP2/CP3/CP4 и downstream F1-29/F1-22/P08/P43 — не входят в этот адаптер.
