# Отчёт о возврате SFA-P38B-DEV-R1

Граница этой работы: `CATALOG_TO_F128_COMPONENT_ONLY`.
Техническая ревизия R1. Редакция передачи H2-AUDIT-FIX1.
Живая система, SQL и реальная отправка здесь не заявляются готовыми.

## Что сделано

Добавлен один модуль `source/first_materials_integration/catalog_config.py`.
Функция `make_catalog_config_resolver(service, client_id, catalog_version, clock)`
возвращает `resolver(campaign_id)`. Конструктор только проверяет аргументы.
Каждый вызов заново читает каталог через принятый `trusted_raw_config` и отдаёт
независимую копию одного поля `raw_config`.

Каталог `first_materials_integration` — namespace-пакет: `__init__.py` не создавался.
Защищённые 90 файлов не изменялись. Старые protected-файлы поверх этого комплекта не накладывались.
Файл `AGENTS.md` в рабочей папке, в комплекте и в корне GitHub на момент работы отсутствовал.
База уже была в GitHub коммитом `cecad64a1d595615b5156cc399ac7ab6b9fc1d32` и побайтно совпала с локальным ZIP, поэтому второй базовый коммит не создавался.

## Среда фактических запусков

- Python 3.12.8 (tags/v3.12.8:2dc476b, Dec  3 2024, 19:30:04) [MSC v.1942 64 bit (AMD64)]
- ОС Windows-11-10.0.26300-SP0
- Команда каждого режима: `python -B RUN_CHECKS.py <integrity|baseline|acceptance|candidate>`
- SHA-256 исходного ZIP: `e6208caa91704c67b052f65681f0b59df54aaf5adf4af79fc67c54fddb382a7d`
- SHA-256 реализации после проверок: `b678ea0499ba737ced73e239e9ff9b5034a15926cdc10c04101a923d6ea8bd78`
- SHA-256 собственных тестов: `2560fd7d65d91686e0722e520e99f0a575abf75dae0e857255e802c4c4e8df16`

## До добавления реализации

Чистый subprocess-прогон неизменённого ZIP:

integrity exit=0 stdout={"status": "PASS", "changed": []}
baseline exit=0 stdout={"status": "PASS", "tests_run": 186, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
acceptance exit=3 stdout=MISSING_IMPLEMENTATION: source\first_materials_integration\catalog_config.py
candidate exit=4 stdout=MISSING_CANDIDATE_TESTS

Это ожидаемое состояние комплекта до кода: целостность и база зелёные, реализации и собственных тестов ещё нет.

## Два чистых прогона

В каждом прогоне ZIP распакован заново. Поверх него положены только
`catalog_config.py` и `candidate_tests/test_catalog_config.py`.
После тестов другие файлы исходного ZIP не появились и не изменились.
Все 90 защищённых hash совпали и до тестов, и после них.
Hash реализации в обеих копиях равен hash проверенного файла.

| Прогон | integrity | baseline | acceptance | candidate | integrity после тестов |
| --- | --- | --- | --- | --- | --- |
| 1 | PASS, exit 0 | PASS, 186 тестов, exit 0 | PASS, 13 тестов, exit 0 | PASS, 22 теста, exit 0 | PASS, exit 0 |
| 2 | PASS, exit 0 | PASS, 186 тестов, exit 0 | PASS, 13 тестов, exit 0 | PASS, 22 теста, exit 0 | PASS, exit 0 |

Пропусков, expected failures и unexpected successes не было: в каждом JSON `skipped=0`.
Сырые stdout, stderr и коды выхода лежат в `raw_logs/clean_run_1/` и `raw_logs/clean_run_2/`.

## Что проверялось по-настоящему

Положительный путь шёл через реальный `CatalogService`, реальный `trusted_raw_config` и реальный `resolve_campaign_projection`. Заглушки использовались точечно: чтобы сосчитать вызовы или подставить один отказ.
Проверены неверные типы и подклассы, границы `is_id` без его ужесточения, UUID, наивные часы, чужой клиент, отсутствие authentication и capability, смена прав, revoke, expiry, повторное чтение, исходное исключение consumer и независимость копии результата.
`release_mode` в проекции остался `NO_OUTBOUND`.

Отдельно: в Python 3.12 нельзя подменить `datetime.now` у неизменяемого класса `datetime`. Поэтому запрет системных часов проверен так: в исходнике модуля нет вызовов `now`/`utcnow`/`today`, а во время реального чтения `time.time`, `open` и `socket.socket` были подменены и не вызывались.

## Patch

`return.patch` содержит реализацию, собственные тесты, `CHANGELOG.md` и `TRACEABILITY.json`.
SHA-256 patch: `56b93887762ba3a47fef0a17aaa8ecf3ff94006106459eef8da1679ccc452f41`.
Проверка применимости: `git -c core.autocrlf=false apply --check` и затем `git -c core.autocrlf=false apply` к базе `origin/main`. Оба завершились с кодом 0. Одноразовый флаг нужен только для сверки байтов: глобальный autocrlf этой машины иначе записывает CRLF, хотя в репозитории стоит `* -text` и файлы хранятся как LF. Конфигурация Git не изменялась.
Полученные четыре файла побайтно совпали с проверенными. Подробности: `raw_logs/patch_apply.txt`.

SHA-256 самого возвратного ZIP в этот отчёт не записывается: отчёт лежит внутри ZIP, и запись hash изменила бы архив. Hash публикуется в корневом README репозитория.

## Ограничения

- macOS: NOT_RUN. Запуски были на Windows 11.
- PostgreSQL: NOT_RUN. SQL этим заданием запрещён.
- installed/connected acceptance: NOT_RUN. Это шаг следующего интегратора.
- production-установка, credentials, системная конфигурация и реальные отправки: не выполнялись.
- B8 CP2/CP3/CP4, F1-29 ingest, F1-22, P08 и P43: NOT_IN_SCOPE. Они не перенесены в этот адаптер и не объявлены выполненными.

Предложение подключения и его границы: `raw_logs/INTEGRATION_PROPOSAL.md`.
