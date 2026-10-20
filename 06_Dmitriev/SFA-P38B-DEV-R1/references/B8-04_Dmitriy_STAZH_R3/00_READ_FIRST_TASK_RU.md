# B8-04 — Подключение исследования, квалификации и предложения

Исполнитель: **Дмитрий стажер**. Проект: Sales Manager FIRST. Ревизия READY_R3.

**Готово к разработке отдельного компонента (READY_TO_DEVELOP).** Это самостоятельное ТЗ с исходниками, действующими контрактами, точным новым wrapper ABI и исполняемыми проверками. Это не отчёт о готовом коде, не разрешение реальных отправок, не приёмка зависимостей и не подтверждение установки. Внешняя выдача/получение кандидатом не выполнялись.

## Что нужно разработать

Закрыть P05/P06: approved research yields qualified lead and exact bound materials saved via existing consumer.

prepare reads catalog.resolve and d1.event using scope+event_id, rejects terminal authority or unapproved fact/template/reference. Calls existing F129 materializer/qualification and existing locale renderer through f129.materialize, not new renderer/research engine. PRODUCT_INFO/PRESENTATION only in V1; event must be informational HUMAN_QUESTION, INTEREST routed to handoff, never continuing sale. Response data={request_id,material_ref,catalog_version}; material hash/locale/pins/approved facts persisted through materials.save adapter before dispatch.propose. Stable request same source bytes => REPLAY; changed input=>CONFLICT. No direct provider. Presentation attachment comes from approved artifact ref, no invented attachment or link. F129 unavailable=>DEPENDENCY_UNAVAILABLE, no replacement. prepare_initial(scope:InitialScope,request_id,candidate_ref,assessment_ref,catalog_version) preserves original initial research→qualification→materials→AUTO queue chain. Trusted refs resolve exact F129 candidate/assessment/binding/policy; f129.qualify invokes existing qualify_candidate. Only QUALIFIED_FOR_PREPARATION continues via f130.materialize_initial→materials.save→dispatch.propose(kind INITIAL_OUTREACH); NEEDS_REVIEW/NOT_QUALIFIED yields BLOCKED with verdict, no materials/send. Scope has five original F114 keys with thread_id=null for initial SEND; never fake provider thread. Initial operation does not require an inbound HUMAN_QUESTION. Product question prepare remains as above.

## Граница первой версии

FIRST заранее настраивается на компанию и продукт/услугу. Сам отвечает по утверждённым материалам и отправляет подходящие презентации. Информационный запрос (например, «пришлите презентацию»/«уточните возможности») сам по себе не означает INTEREST. Первый подтверждённый интерес/желание следующего шага → durable handoff человеку и остановка дальнейшей клиентской автоматизации. Продолжение продажи/возражения позже подключаются как новые версии без потери истории. «Не пишите мне» прекращает работу с достоверно известным клиентом, отменяет ожидающие сообщения; только результат уже начатой необратимой отправки может дописаться. Наличие одного claim не разрешает новый вызов после STOP. Позднее подтверждение — запись результата, без повторной отправки.

## Точная граница файлов

Разрешено создавать только solution/first_materials_runtime/**, tests/first_materials_runtime/**, integration_proposal/B8-04.patch. SQL proposal резерв b8r2.04.0001 в своём модуле; он не применяется автоматически и не присваивает общие serial номера. Исходники reference_source и reference_d1 неизменны. Shared sales_manager.py/sales_store.py/main.py/worker.py/worker_prod.py/task_store.py/migrate.py и все существующие owner state меняет только центральный интегратор. Чужие назначения не отменять/не дублировать.

## Порядок начала

1. CONTRACT.json содержит точные операции, ключи, capabilities и scope именно этой задачи. SHARED_CONTRACT_R2.md задаёт порядок ошибок/locks/ownership. PORT_CONTRACTS.json и PORT_MAPPING_R2.md задают trusted producer/adapter codecs.
2. `python ACCEPTANCE_RUNNER.py cp0` — baseline/fixtures/source validators.
3. Писать собственный модуль; `python ACCEPTANCE_RUNNER.py cp1 --module first_materials_runtime.api`. До реализации ожидается NOT_IMPLEMENTED exit3; это не дефект выданного пакета и не PASS новой работы.
4. CHECKPOINTS_AND_RETURN_RU.md задаёт CP2 PostgreSQL/CP3 интегратор/CP4 аудит и состав возврата.

## Зависимости и доказательства

- R2 PRODUCT_INFO/PRESENTATION consumer ABI frozen; F130 source reused.
- Интеграция: exact accepted F129 текущего исполнителя и B8-01 approved raw bundle, trusted assessment/source bindings.

Исторические proposals/NOT_APPROVED в reference_contracts сохраняются как первоисточник. Только R2 новые границы/решения имеют приоритет в явно указанной области; старые F1 API не переписываются молча. DEPENDENCIES.json уточняет реальные gates, включая незавершённый F115 и sole-D1-owner ACTIVE append extension. Все facade mocks — OFFLINE, реальные principals/числовые политики до activation, без скрытых defaults. Синтетический callback не подтверждает наличие production backend.

Возвращать код своего участка, tests и raw evidence; недостаточно отчёта/аудита без реализации. Критерии из исходной карточки остаются обязательны в применимой V1 области:

- Foreign scope/revoked research -> no save
- Stale config between read/commit -> rollback
- Actual qualify -> materialize -> save PG and exact reload
- No changed subject/body whitespace or fallback language
- Existing AUTO->SEND_QUEUED permitted but process_send makes zero provider calls under hold


R3 normative clarification: read MATERIALS_CODEC_R3.md. R3 closes input/ownership ambiguities; supplied tooling is PROVIDED, not candidate implementation. Return evidence under return/** is allowed.
