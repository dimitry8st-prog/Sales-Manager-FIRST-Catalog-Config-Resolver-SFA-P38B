# SFA-P38B-DEV-R1: frozen component contract

## API
`make_catalog_config_resolver(service, *, client_id, catalog_version, clock) -> callable(campaign_id)`.
`CatalogConfigError(ValueError)` має `.code`; str(error) тільки code.
Constructor: `service.execute` і clock callable; client_id/catalog_version exact str валідні за existing `first_campaign_catalog.api.is_id`; інакше INVALID_RESOLVER_CONFIGURATION. Не викликати service чи clock у constructor. Принципал/автентифікація належить переданому existing service; adapter ніколи не створює auth, capability або approval.
На кожний виклик resolver:
1. campaign_id exact str canonical lowercase UUID; інакше INVALID_CAMPAIGN_ID до clock/service. Scope рівно {client_id: pinned client_id,campaign_id: input id}. Конфігурацію/версію/клієнта з task payload не брати.
2. Один clock() → now, який має бути exact aware datetime, інакше INVALID_CLOCK. Original clock exception проходить тим самим об'єктом. Ніякого system clock/environment fallback.
3. Рівно один `first_campaign_catalog.consumer.trusted_raw_config(service, scope, catalog_version, now=now)` через public module import. Не переписувати validator/resolve DTO/approval логіку, не кешувати попередній success. Original exceptions проходять тим самим об'єктом. Existing service повторно перевіряє authentication, scope, capability, revoke і expiry; existing consumer повторно валідовує raw bundle.
4. Повернути незалежний deepcopy тільки result['raw_config']; ніяких додаткових полів. Ніколи не змінювати вхід або додавати release authority. Використати цей callable без wrapper API change у `sales_runtime_binding.resolve_campaign_projection(campaign,resolve_config=resolver,now=explicit_now)`; F128/F112 лишаються незмінні.
Компонент не визначає current catalog version: host інтеграція створює resolver із фактичним pin кожної операції. Старий resolver завжди читає свій pin; зміна версії → новий resolver. Перевірка чинної dispatch authority залишається фінальному gate, не підміняється читанням історичної версії. F128 now та reader clock повинні походити від одного trusted operation clock в assembly; пакет тестує явні синтетичні часові точки.
