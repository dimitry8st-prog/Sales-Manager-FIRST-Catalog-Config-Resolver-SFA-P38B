# Изменения SFA-P38B-DEV-R1

- Добавлен новый `source/first_materials_integration/catalog_config.py`: точный
  контракт фабрики resolver и ошибки, zero-effect constructor, проверка campaign
  до часов/сервиса, один injected clock и один настоящий public consumer на чтение.
- Возвращается независимый raw_config; закреплённые scope/version не меняются;
  кеш, fallback/retry и дополнительные разрешения отсутствуют.
- Добавлены собственные исполняемые candidate tests и карта TRACEABILITY.
- Выполнены две чистые проверки; фактические counts, окружение и результаты
  записаны в raw_logs/RETURN_REPORT.md, commands.json и сырые stdout/stderr.
- return.patch применён к чистой исходной базе; SHA-256 до/после и ZIP проверяются.
- Все выданные файлы, включая 90 protected, source dependencies, checks, fixtures,
  references, evidence, RETURN.md и административные поля, оставлены побайтно.
- Runtime/production integration не выполнялась. H2-AUDIT-FIX1 сохранён;
  техническая редакция остаётся R1, прежние компоненты и их владельцы не заменены.
