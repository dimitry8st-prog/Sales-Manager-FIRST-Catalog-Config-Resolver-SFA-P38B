# F1-29 — Константин / Constantin

Одно самостоятельное ТЗ. Цель: подключаемый gate квалификации перед ingest discovery lead.

1. Прочитать accepted qualify_candidate signature и positive.json; не переделывать F110. Проверить checksum, запустить исходный RED.
2. Реализовать API и проверку двух trusted callable до любого port. Снять независимые snapshots mutable inputs.
3. Вызвать resolve_assessment с копией candidate; никаких metadata-derived approved/provider booleans.
4. Передать trusted assessment в F110 вместе с точными binding, policy, now. Сохранить полное qualification, reason_codes и provenance без синтеза.
5. Вызвать ingest только для QUALIFIED_FOR_PREPARATION, передав независимые candidate и qualification. Вернуть две точные keys; иначе None и ноль записей.
6. Проверить stale/unconfirmed/provider_only, scope mismatch, resolver failure, DuplicateLead propagation и mutable callback. Дополнить свои tests, подготовить возврат с raw logs.

Приёмка: точный CONTRACT.json, целые protected files, PASS public+собственные meaningful tests, инструкции интегратору, полный воспроизводимый возврат. Компонентный PASS не доказывает production integration или закрытие FIRST.

## Исправленная передача H2 (technical ABI R1)
Прямое подключение F128 projection к F129 binding запрещено: F112 возвращает 18 полей FIRST_CAMPAIGN_PROJECTION_V1, F110 принимает ровно пять полей FIRST_QUALIFICATION_BINDING_V1. Инженер внедрения владеет механическим mapper reference/qualification_binding_mapper.py: schema_version заменяется на FIRST_QUALIFICATION_BINDING_V1, а client_id/runtime_campaign_id/offer_id/binding_version копируются без преобразований. Остальная projection сохраняется для других consumers; её не обрезать in-place. Новый кандидатский adapter API не меняется.

```python
projection = resolve_campaign_projection(campaign, resolve_config=trusted_config_resolver, now=now)
qualification_binding = projection_to_qualification_binding(projection)
result = qualify_and_ingest(candidate, binding=qualification_binding, policy=trusted_policy,
    resolve_assessment=trusted_assessment_resolver, ingest=reviewed_ingest_closure, now=now)
```
Код mapper поставлен как frozen integration-owner reference, не задание кандидату и не изменение accepted F110/F112. tests/test_integration_mapping.py доказывает actual F112→mapper→actual F110; внешний control proof отдельно проверяет ту же цепь через candidate ABI с контрольными реализациями. Scaffolds в пакете намеренно остаются RED.

F128 projection НЕ содержит raw approved_facts с текстами/source_ref и полного offer. F130 должен получать исходный trusted F105 config отдельно через серверный resolver из того же authoritative campaign/binding_version, а не реконструировать config из projection. Никаких task-payload fallback или выдуманных фактов. Источник config, candidate identity, assessment/policy producers ещё не подключены. Пакет остаётся PREPARED_NOT_ISSUED, integration NOT_CONNECTED.
