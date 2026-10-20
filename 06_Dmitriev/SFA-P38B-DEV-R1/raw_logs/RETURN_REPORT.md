# Возврат SFA-P38B-DEV-R1

Статус: **OFFLINE_COMPONENT_CHECKS_PASS**. Подтверждена только граница
`CATALOG_TO_F128_COMPONENT_ONLY`; это авторская проверка, не независимая приёмка.

## Реализация

Добавлен ровно один продуктовый модуль `source/first_materials_integration/catalog_config.py`.
`make_catalog_config_resolver(service, *, client_id, catalog_version, clock)`
проверяет конфигурацию без обращения к часам/сервису и возвращает resolver.
Каждое чтение проверяет канонический UUID, один раз получает точный aware datetime
из переданного clock, один раз вызывает настоящий public
`first_campaign_catalog.consumer.trusted_raw_config` и возвращает независимый
deepcopy только `raw_config`. Auth/capability/scope/revoke/expiry и bundle validation
остаются у принятых service/consumer. Конфигурация из task/campaign payload не читается.
Кеш, retry, fallback, новые authority и системное время не добавлены.
Исключения clock/consumer проходят исходным объектом.

## Фактическая проверка

Python: 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]. ОС: Linux-6.18.55-x86_64-with-glibc2.39.
Исходный ZIP SHA-256: e6208caa91704c67b052f65681f0b59df54aaf5adf4af79fc67c54fddb382a7d.

| Проверка | Чистая копия 1 | Чистая копия 2 |
| --- | ---: | ---: |
| Integrity до и после | PASS | PASS |
| Baseline | 186 PASS | 186 PASS |
| Acceptance | 13 PASS | 13 PASS |
| Candidate | 29 PASS | 29 PASS |
| Всего тестов | 228 PASS | 228 PASS |
| Skips/expected failures/unexpected successes | 0/0/0 | 0/0/0 |

Сохранены все 90 protected-файлов и все 92 исходных файла архива,
включая внешний README и защищённый манифест. `__init__.py` не добавлен.
Начальные acceptance exit 3 и candidate exit 4 — ожидаемое отсутствие реализации
и собственных тестов, сохранённое в `initial_commands.json`, а не PASS компонента.

Команды, cwd, Python/platform, время, stdout/stderr и exit codes:
`commands.json`; исходные команды — `initial_commands.json`.
Сырые логи обеих копий — `clean1_*.log` и `clean2_*.log`.
Ненулевой discovery подтверждён `test_inventory.json` и raw inventory logs.
`TRACEABILITY.json` связывает контракт, код, существующие тесты и сырые логи.
`return.patch` проверен через git apply --check и применён к отдельной исходной
распаковке; результат побайтно равен протестированным модулю и тестам.
`SHA256_BEFORE.json` содержит исходные байты; `SHA256_AFTER.json` перечисляет
SHA-256 всех файлов возврата кроме самого себя. Пути в этих файлах от корня ZIP.
Хеши подтверждают identity/целостность, не correctness или trust.

## Воспроизведение

Из `06_Dmitriev/SFA-P38B-DEV-R1` выполнить:

```bash
python -B RUN_CHECKS.py integrity
python -B RUN_CHECKS.py baseline
python -B RUN_CHECKS.py acceptance
python -B RUN_CHECKS.py candidate
python -B RUN_CHECKS.py integrity
```

Python стандартная библиотека; зависимости из выданного source.
Для Windows можно использовать `py -3.12 -B` вместо `python -B`.

## Подключение и откат — предложение интегратору

После независимой приёмки компонентного возврата интегратор проверяет актуальный
HEAD/hash/dependency/path collision и владельца нового пути. Проверенный backup и
фактический restore предшествуют additive установке только согласованного own файла.
Host передаёт доверенный существующий CatalogService, закреплённые client/version
и operation clock; F128 explicit_now и reader clock происходят от одной доверенной
временной точки. Адаптер не меняет приватный `service._ports.now`.
Новая версия каталога требует нового resolver; старый всегда читает свой pin.
Текущая dispatch authority, trusted source/producer и актуальность policy остаются
у host/final gates. Исторический pin сам по себе не разрешает отправку.
На exact installed bytes повторяются baseline/component и независимый installed review.
При collision установку останавливают. Rollback затрагивает только own файл с
совпадающим принятым SHA и собственные tests/docs по проверенному backup;
чужие изменения не удаляются. Shared main/store/routing/SQL/provider не меняются.

## Ограничения и NOT_RUN

- Независимая приёмка заказчиком: NOT_RUN — выполняется после передачи.
- Native Windows и macOS: NOT_RUN — фактическая среда этого прогона Linux.
- Реальный PostgreSQL/SQL acceptance: NOT_RUN — SQL/network не входят в разрешённую
  компонентную границу; исторические B8 CP2/CP3/CP4 этим возвратом не закрываются.
- Actual SOURCE installation, backup/restore/rollback, installed/connected review:
  NOT_RUN — отдельная работа интегратора, рабочая система не изменялась.
- Production activation, provider/outbound, server-owned provenance/currentness
  и live principal/final authority gates: NOT_RUN — не предоставлены и не вызываются.
- Пакет не реализует F1-29 qualification/ingest, F1-22R2 checkpoint bridge,
  materials.save/dispatch и transport; действующие владельцы сохранены.
- Поля исходного TASK_IDENTITY и имена получателя сохранены как выданы;
  исторические административные статусы самостоятельно не исправлялись.

## Проверка закрытого ZIP

Полный ZIP с исходным корнем `06_Dmitriev` проверяется после закрытия дважды:
CRC, безопасные уникальные пути, exact manifest, исходные/protected байты,
совпадение с протестированным кодом и свежая распаковка.
Итоговый SHA-256 ZIP и фактический результат этой проверки находятся снаружи
архива в `artifacts/SFA-P38B-DEV-R1_RETURN_R1.validation.json`, чтобы избежать
самоссылки хеша. Наличие этого раздела не заменяет внешний фактический PASS.
