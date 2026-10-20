# B8-01 — Доверенный каталог и согласованное разрешение конфигурации

Исполнитель: **Владимир New**. Проект: Sales Manager FIRST. Исправленная выдача **READY_R3** взамен READY_R2. Это новое задание на компонент, не готовое решение кандидата, не разрешение установки или отправок.

## Что разработать

Собственный `first_campaign_catalog`: publish/resolve/revoke утверждённых immutable версий company/product configuration, registry и полных языковых packs. Runtime role только читает; publish/revoke доступны authenticated publisher capability. Одна конфигурация и pins на цикл, без смешивания версий. Durable replay/CAS/concurrency/restart/rollback; отзыв/публикация atomically invalidates все затронутые InitialScope/LeadScope через sole integrator facade. Ни D1/F115 replacement, ни shared runtime edits кандидат не делает.

## Что исправлено в нашем пакете

R2 не доставлял packs обязательному F106 validator и не определял raw byte verification/consumer projection. В R3 полный **ApprovedBundle_R3** передаёт точные base64 UTF8 config/registry/pack bytes с индивидуальными SHA256. PROVIDED чистый codec вызывает неизменные исходные F105/F106 validators; PROVIDED consumer adapter сохраняет прежний `{version,bundle_ref,approved}` port. Добавлены negative/rollback/ref conflict/старый revoke и two-publisher CAS checks. Эти исправления входов не являются работой кандидата.

## Прочитать и запустить

1. `CONTRACT.json`, `CATALOG_R3_SPEC.md`, `SHARED_CONTRACT_R3.md`, `PORT_CONTRACTS.json`, `PORT_MAPPING_R3.md`.
2. Из корня пакета: `python ACCEPTANCE_RUNNER.py cp0`. Никаких ручных PYTHONPATH для этой команды не нужно. Проверяет целостность, действительные positive inputs, codec/adapter negative probes и исходные F1 suites.
3. Создать `solution/first_campaign_catalog/api.py`: `create_service(ports).execute(operation,request) -> {status,data}`. PROVIDED `tooling/` не реализует service/storage/auth/CAS. Исходные validators доступны harness через reference_source; в собственных test commands указывать корень и reference_source в PYTHONPATH явно.
4. `python ACCEPTANCE_RUNNER.py cp1 --module first_campaign_catalog.api`. До реализации **NOT_IMPLEMENTED exit3 ожидаем**, это не PASS и не дефект архива. После реализации должны пройти fixtures и CAS probe; добавить собственные meaningful tests.
5. `CHECKPOINTS_AND_RETURN_RU.md`: CP2 real PG, CP3 отдельный интегратор и CP4 аудит не закрываются offline fake ports.

## Границы и возврат

Создавать/менять только `solution/first_campaign_catalog/**`, `tests/first_campaign_catalog/**`, `integration_proposal/B8-01.patch`, `return/**`. В return — CHANGELOG, собственные raw logs/evidence, requirement→file→test mapping, manifests и инструкция подключения/отката. PROVIDED contracts/fixtures/tooling/reference_source/reference_d1/reference_contracts не менять. Migration reservation `b8r2.01.0001` сохранён как ранее выделенный ID, это не версия пакета; proposal не применяется автоматически.

FIRST V1 заранее настраивается на компанию/продукт; отвечает по approved материалам, информационный вопрос сам по себе не INTEREST. Первый подтверждённый INTEREST → durable handoff человеку и остановка клиентской автоматизации; OPTOUT прекращает работу с достоверно известным клиентом. Поздняя evidence только фиксирует результат, не разрешает resend. Точные неизменные бизнесправила — shared contract.

NO_OUTBOUND. Реальные principals/source mappings, migration acceptance, sole authority multi-scope adapter и owner addenda — gates интегратора. Reference base — исторический snapshot, не текущая установка. Состав исправлений R3 не меняет владельцев других назначений. Объём CP2/integration нельзя скрыто объявить выполненным.
