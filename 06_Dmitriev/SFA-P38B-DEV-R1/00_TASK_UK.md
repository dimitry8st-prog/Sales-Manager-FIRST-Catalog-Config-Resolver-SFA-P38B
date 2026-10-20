# SFA-P38B-DEV-R1 — Довірений resolver каталогу для runtime campaign binding

Відсутня конкретна композиція між accepted CatalogService/consumer.trusted_raw_config і existing F128 resolve_config callback. Реалізувати тільки цей read-only adapter із повторною перевіркою кожного читання.

Самостійний результат — новий виконуваний компонент із власними тестами. Не потрібно чекати загальної інтеграції, щоб реалізувати цей зафіксований seam. Пакет передається без призначеного виконавця; кандидата визначає власник. Підготовка не є видачею/початком/прийманням.

## Точний обсяг

Реалізуйте `source/first_materials_integration/catalog_config.py` згідно CONTRACT.md. Це розвиток інтеграційного залишку SFA-P38, а не заміна B8-01/B8-04/F1-29/F1-22/SM06. Всі accepted modules у source/ read-only. Дозволені додаткові файли: candidate_tests/test*.py, CHANGELOG.md, TRACEABILITY.json, raw_logs/**, return.patch. Каталог `first_materials_integration` — PEP420 namespace: не створюйте спільний __init__.py.

## Робота

1. Прочитайте CONTRACT.md, INTEGRATION.md та references. Прогоніть python3 RUN_CHECKS.py integrity і baseline.
2. Додайте рівно свій модуль. Accepted helpers викликайте через їх public APIs, не переносіть валідацію чи стан у копії.
3. Прогоніть acceptance і власні candidate tests, у т.ч. негативні вектори нижче. Не міняйте provided checks заради PASS.
4. Поверніть один ZIP зі збереженими шляхами, кодом/patch, hashes, командами/exit/raw output, TRACEABILITY і відомими обмеженнями.

## Приймання

Обов'язкові integrity, baseline, acceptance і власні тести — PASS без skips. До реалізації acceptance навмисно exit3 MISSING_IMPLEMENTATION; це НЕ defect залежностей. Жодного provider/network/production/SQL/system config виклику. Офлайн PASS закриває тільки CATALOG_TO_F128_COMPONENT_ONLY; installed/connected acceptance лишається інтегратору після прийнятого повернення.

Очікувані negative vectors та точні результати — CONTRACT.md і checks/test_acceptance.py. Додати meaningful own tests на межі Unicode, mutable inputs/results, exceptions, повторний виклик, підміну scope/pins. Hash означає identity, не correctness або trust.

RETURN.md — захищена інструкція формату повернення, не файл звіту. Звіт збережіть у вже дозволеному raw_logs/RETURN_REPORT.md.
