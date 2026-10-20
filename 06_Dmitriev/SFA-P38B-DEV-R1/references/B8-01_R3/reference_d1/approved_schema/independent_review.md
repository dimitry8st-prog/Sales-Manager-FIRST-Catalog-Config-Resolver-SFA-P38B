# Независимый review схемы хранения D1

Verdict: **PASS_STORAGE_DESIGN** — схема и граница самостоятельной реализации репозитория. Не SQL/runtime PASS, не приёмка реализации и не утверждение D2. D1 уже одобрено владельцем, повторное согласование D1 не требуется.

Аудитор прочитал текущие STORAGE_SCHEMA_R1.md, reference_ddl.sql, READ_FIRST_RU.md, TASK_CONTRACT.md и D1_APPROVAL.json; сверил с предшествующим snapshot contract/frozen F115 seam. Код реализации не писал; SQL не применял, продуктовые/DB-тесты не запускал. Все будущие PostgreSQL проверки остаются NOT_RUN.

Scope связан с immutable authority_id и unique полным scope; composite FK предотвращают ссылки на чужие authority records. Global snapshot_id обеспечивает однозначный check_current, global handoff_event_id соответствует более узкому ключу F115. Immutable snapshot содержит membership/bytes целиком: поздние relational membership additions исключены.

Revision0 определён заблокированным skeleton без children. Первое полноценное состояние revision1. Writer берёт authority lock до FK inserts, публикует весь r+1 и pointer в одной транзакции; capture использует тот же lock. INSERT child triggers требуют current+1 и не позволяют позднее дополнить старый cut. Multi-authority порядок сортирован; lease/journal locks не смешиваются. Concurrent init обрабатывается unique scope conflict и чтением прежнего authority без reset/re-ID.

Полный cut использует последнюю версию каждого сообщения<=r без LIMIT100; correction/backfill создают новую revision, старый snapshot остаётся точным. Complete checkpoint не выдан за полноту внешнего ящика. Source markers и fixtures не заменяют доверенных producers. Canonical bytes/hash/JSONB equality, exact nested types/scope, role-kind/required dependencies, active sequence uniqueness, отсутствие orphan/future revision и разрешённые business transitions прямо отнесены к repository validation, а не вымышленным SQL guarantees.

Triggers не защищают от владельца таблиц/TRUNCATE/DDL: привилегии и corruption tests явно остаются обязательными. Reference namespace не резервирует реальный schema name; migration additive, fail-on-drift. Recovery отключает новый путь и сохраняет committed durable tables; unconditional DROP и удаление PREPARED не предлагаются. Backup/restore не выданы за выполненные.

Учтены замечания до фиксации хешей: global snapshot uniqueness; revision0/current+1 bootstrap; lock-first для standalone trust/checkpoint; concurrent init idempotency; historical registry115 обозначен input baseline, D1approval — текущее решение. Неустранённых противоречий для design acceptance не найдено.

Минимальный следующий продуктовый шаг обоснован: новый authority/history/snapshot repository с disposable PostgreSQL concurrency/restart/recovery tests, без journal calls и без synthetic journal в SOURCE. Непринятый F115 не препятствует проверке собственной T1storage boundary; он обязателен до journal bridge. Перед реализацией нужны свежая namespace/collision сверка и точные file reservations/runner/roles. Реальные ingestion/approval/decision producer contracts и F117 нужны до рабочего подключения. D2 snapshot-to-guard mapping, глобальная инвалидация/expiry и любой dispatch/HUMAN остаются отдельно не принятыми.

Новые назначения/прогресс/готовность продукта не заявлены; 35%,0/13,+0 сохранены. SHA256:

```json
{
  "STORAGE_SCHEMA_R1.md": "d44a676b78b05907e165ee651401b86984d59d86e3fc6fd9900b7e3a8b15c195",
  "reference_ddl.sql": "02aa68fcb68fdf5d93269f86f0abdf1f8b7115d7935472fd2b39103ae0fee52b",
  "READ_FIRST_RU.md": "8148e318729a1090819301954b7f33fb71b12edf2e4dbff608b12e002d3db9bb",
  "TASK_CONTRACT.md": "8247dde84dc06c0ee46493758301d0825467b488f7b0087c2ebe710a1fe24538",
  "D1_APPROVAL.json": "13cb2bb7aaa2bcd52014293f77f233f07e5a4cc85db31592db279848aefc8ac6"
}
```

## Итоговая документарная фиксация

PASS: новый header согласован со схемой и README;8таблиц, unique/compositeFK и ограничения SQL описаны без повышения до runtime PASS. D1approved, D2notapproved; DDLNOT_APPLIED и PGtests/restoreNOT_RUN сохранены. Concurrent initialization clarification фактически присутствует в STORAGE_SCHEMA_R1.md. Проверен точный суффикс v116:296751байт; его v115суффикс тоже сохранён. Сохранение будущей версии/ZIP во внешнем хранилище этим review не подтверждается. Итоговые хеши:

```json
{
  "STORAGE_SCHEMA_R1.md": {
    "bytes": 19375,
    "sha256": "d44a676b78b05907e165ee651401b86984d59d86e3fc6fd9900b7e3a8b15c195"
  },
  "reference_ddl.sql": {
    "bytes": 11090,
    "sha256": "02aa68fcb68fdf5d93269f86f0abdf1f8b7115d7935472fd2b39103ae0fee52b"
  },
  "READ_FIRST_RU.md": {
    "bytes": 3264,
    "sha256": "8148e318729a1090819301954b7f33fb71b12edf2e4dbff608b12e002d3db9bb"
  },
  "Sales_Manager_FIRST_Developer_Register.md": {
    "bytes": 300825,
    "sha256": "eb9c1b1bb75d8df43ba7a05de74763ecca12fcf3a23db56d14c3a82e9ee10f36"
  },
  "Developer_Register_v116_preserved.md": {
    "bytes": 296751,
    "sha256": "a84c60422ce139e3b0a84bbffac60bcd7116e15b7b7195b1f7961bb925a88f47"
  }
}
```
