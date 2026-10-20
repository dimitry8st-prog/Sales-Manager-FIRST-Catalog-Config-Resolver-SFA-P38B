# SFA-P38B — resolver конфигурации каталога для F128

Компонент проекта Sales Manager FIRST связывает существующий каталог кампаний с публичным callback `resolve_config` модуля F128. При каждом обращении он читает закреплённую версию через настоящий catalog consumer и возвращает независимую конфигурацию. Принятые модули остаются неизменными.

Статус: **OFFLINE_COMPONENT_CHECKS_PASS**. Подготовлен возврат для компонентной приёмки в границе `CATALOG_TO_F128_COMPONENT_ONLY`.

## Пакет сдачи

- [SFA-P38B-DEV-R1_RETURN_R1.zip](artifacts/SFA-P38B-DEV-R1_RETURN_R1.zip?raw=true) — полный комплект с исходной структурой `06_Dmitriev/`, реализацией, тестами, patch, отчётом и сырыми логами.
- [Проверка закрытого ZIP](artifacts/SFA-P38B-DEV-R1_RETURN_R1.validation.json).
- [Независимое применение patch из ZIP](artifacts/SFA-P38B-DEV-R1_RETURN_R1.independent-review.json).
- [Исходный выданный архив](06_Dmitriev.zip) — сохранён без изменений, редакция передачи H2-AUDIT-FIX1, техническая R1.

SHA-256 возвратного ZIP:

```text
633c81da29bf73877c2558dfa928f8e9ff40905ec6ad5e535f1fa363e3092562
```

## Как работает

Новый продуктовый файл: [catalog_config.py](06_Dmitriev/SFA-P38B-DEV-R1/source/first_materials_integration/catalog_config.py).

```python
make_catalog_config_resolver(service, *, client_id, catalog_version, clock)
```

Фабрика проверяет callable-зависимости и идентификаторы через существующий `api.is_id`. Конструирование не вызывает сервис или часы. Возвращённый `resolver(campaign_id)` выполняет следующие действия:

1. Проверяет точную строку с каноническим lowercase UUID кампании.
2. Один раз получает точный aware `datetime` из переданного `clock`.
3. Один раз вызывает настоящий `consumer.trusted_raw_config` с закреплённым клиентом и версией.
4. Возвращает глубокую независимую копию только `raw_config`.

Аутентификацию, capability, tenant/scope, отзыв, сроки и содержимое bundle повторно проверяют существующие service/consumer. Предыдущий успешный результат не кешируется. Для новой версии каталога host создаёт новый resolver; существующий продолжает читать свой pin.

Ошибки валидации адаптера: `INVALID_RESOLVER_CONFIGURATION`, `INVALID_CAMPAIGN_ID`, `INVALID_CLOCK`. Оригинальные исключения часов и consumer проходят тем же объектом, без retry и подмены результата. Адаптер не создаёт auth/approval и не изменяет приватное состояние сервиса.

Публичный стык с `sales_runtime_binding.resolve_campaign_projection` проверен на настоящих F128/F112 и синтетическом порте хранения. `release_mode` остаётся `NO_OUTBOUND`. Host должен передавать F128 и resolver время одной доверенной операции.

## Фактическая проверка

Среда: Python 3.12.14, Linux, стандартная библиотека. Два прогона выполнены в независимых чистых копиях исходного комплекта с разрешёнными добавлениями.

| Проверка | Чистый прогон 1 | Чистый прогон 2 |
| --- | ---: | ---: |
| Integrity до и после | PASS | PASS |
| Baseline зависимостей | 186 PASS | 186 PASS |
| Предоставленный acceptance | 13 PASS | 13 PASS |
| Собственные candidate tests | 29 PASS | 29 PASS |
| Всего | **228 PASS** | **228 PASS** |
| Skips / expected failures / unexpected successes | 0 / 0 / 0 | 0 / 0 / 0 |

Все 90 защищённых файлов и все 92 исходных файла сохранены побайтно. Общий `__init__.py` не создавался. Собственные тесты проверяют строгие типы/UUID/Unicode, ошибки часов, точный порядок и число вызовов, закреплённые scope/version, отсутствие кеша, изменение auth/revoke/expiry после успеха, повреждённые bundle, независимость вложенных результатов, идентичность исключений и запрет прямого I/O.

Patch применён к исходной базе с проверкой совпадения байтов. ZIP дважды проверен после закрытия: CRC, безопасные пути, точный состав, manifest и совпадение с протестированным кодом. Дополнительно патч из финального ZIP независимо применён к исходному архиву: результат совпал с реализацией и тестами внутри ZIP. В ZIP 142 файла, SHA-manifest содержит остальные 141 файл.

## Повторить проверки

Из корня клонированного репозитория:

```bash
cd 06_Dmitriev/SFA-P38B-DEV-R1
python -B RUN_CHECKS.py integrity
python -B RUN_CHECKS.py baseline
python -B RUN_CHECKS.py acceptance
python -B RUN_CHECKS.py candidate
python -B RUN_CHECKS.py integrity
```

В Windows при необходимости используйте `py -3.12 -B` вместо `python -B`. Отдельные пакеты, БД, ключи и внешние сервисы для компонентных проверок не нужны. Исходные `MISSING_IMPLEMENTATION` exit 3 и `MISSING_CANDIDATE_TESTS` exit 4 сохранены в начальных логах как ожидаемое состояние до реализации.

## Документы и доказательства

- [ТЗ](06_Dmitriev/SFA-P38B-DEV-R1/00_TASK_UK.md), [контракт](06_Dmitriev/SFA-P38B-DEV-R1/CONTRACT.md), [исправления комплекта](06_Dmitriev/SFA-P38B-DEV-R1/AUDIT_FIX_20261020.md).
- [Полный отчёт, ограничения, подключение и откат](06_Dmitriev/SFA-P38B-DEV-R1/raw_logs/RETURN_REPORT.md).
- [Требование → код → тест → сырой лог](06_Dmitriev/SFA-P38B-DEV-R1/TRACEABILITY.json).
- [CHANGELOG](06_Dmitriev/SFA-P38B-DEV-R1/CHANGELOG.md), [return.patch](06_Dmitriev/SFA-P38B-DEV-R1/return.patch).
- [Команды и exit codes](06_Dmitriev/SFA-P38B-DEV-R1/raw_logs/commands.json), [RESULT.json](06_Dmitriev/SFA-P38B-DEV-R1/raw_logs/RESULT.json), [все сырые логи](06_Dmitriev/SFA-P38B-DEV-R1/raw_logs).
- [SHA-256 до](06_Dmitriev/SFA-P38B-DEV-R1/raw_logs/SHA256_BEFORE.json) и [после](06_Dmitriev/SFA-P38B-DEV-R1/raw_logs/SHA256_AFTER.json). Пути в manifest указаны от корня ZIP; manifest исключает только самого себя.

## Границы готовности

Независимая приёмка, native Windows/macOS, реальный PostgreSQL, установка в actual SOURCE, backup/restore/rollback, installed/connected review и production activation обозначены `NOT_RUN` с причинами в отчёте. Эти проверки и внедрение относятся к последующим согласованным этапам. Исторические B8 CP2/CP3/CP4 этим возвратом не закрываются.

Прямые файловые/сетевые/SQL-операции, system clock, shared runtime, credentials и provider/outbound не добавлены. Доверенное происхождение, выбор актуальной версии и финальные разрешения остаются у host/интегратора. Контрольные суммы подтверждают целостность и identity байтов, а не права доступа или готовность всей системы.
