# CHANGELOG

## SFA-P38B-DEV-R1 — чтение каталога для F128

Добавлен один новый модуль: `source/first_materials_integration/catalog_config.py`.

`make_catalog_config_resolver` закрепляет клиент, версию каталога и часы.
Каждый вызов `resolver(campaign_id)` заново читает только `raw_config` через
принятый `first_campaign_catalog.consumer.trusted_raw_config`. Результат — независимая
копия. Кэш, запасной вариант и выбор «текущей» версии не добавлялись.

Каталог `first_materials_integration` оставлен namespace-пакетом PEP 420: общего
`__init__.py` нет.

Добавлены собственные тесты `candidate_tests/test_catalog_config.py`.
Защищённые файлы выданного комплекта не изменялись. Техническая ревизия остаётся R1,
редакция передачи — H2-AUDIT-FIX1.

Этот компонент закрывает только границу `CATALOG_TO_F128_COMPONENT_ONLY`.
