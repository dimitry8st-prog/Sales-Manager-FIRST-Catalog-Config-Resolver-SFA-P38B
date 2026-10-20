# F1-28 — Владимир new

Одно самостоятельное ТЗ. Цель: подключаемая граница серверной binding projection перед discovery/preparation.

1. Прочитать frozen F105/F112 и positive.json. Проверить checksum. Запустить тесты, зафиксировать исходный RED.
2. Реализовать указанную сигнатуру и RuntimeBindingError. Проверять runtime campaign и callable до вызова resolver, в указанном порядке.
3. Получить config только через resolve_config(campaign_id). Выполнить project_campaign_binding(config, now=now). Не повторять валидацию F105 вручную.
4. Проверить runtime scope; вернуть точную независимую проекцию без новых полей, merge с campaign или повышения release_mode.
5. Проверить expiry и ошибки accepted validators, mismatch, malicious campaign.config, resolver failure и отсутствие мутаций. Дополнить собственные тесты неправильных типов и отсутствующего resolver.
6. Проверить import без IO/часов/env, подготовить raw logs, patch/full files и отчёт по RETURN_GUIDE.md.

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
