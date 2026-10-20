# Межа підключення й відновлення

Відсутня конкретна композиція між accepted CatalogService/consumer.trusted_raw_config і existing F128 resolve_config callback. Реалізувати тільки цей read-only adapter із повторною перевіркою кожного читання.

Точний новий шлях: `first_materials_integration/catalog_config.py`. Перед merge окремий інтегратор повторно перевіряє поточний HEAD/hash protected dependencies і відсутність іншого writer цього шляху. У разі collision зупиняє тільки цей merge. Спільні main.py, sales_store.py, runtime routing, schemas/transactions, credentials та чинні призначення не змінюються кандидатом. Пауза контролюючого агента збережена.

Реалізація/компонентне приймання незалежні від runtime activation. Наступний інтегратор підключає готовий adapter у відповідний існуючий injection port; package не надає authority чи trusted producer. Архів лише staging; config adapter лише server-owned CatalogService reader; research adapter лише read_record callback. Реальний owner/source provenance, approved facts, version/currentness policy та live principal підтверджуються окремими P09/P38/P07/P39 gates.

F1-29 qualify_and_ingest залишається чинному виконавцю. Цей resolver не викликає ingest/qualification. Для connected F1-29 потрібно прийняти його повернення. F1-22R2 checkpoint bridge, P08 materials.save/dispatch та P43 transport не реалізовані тут. Жоден із цих downstream блокерів не заважає розробити та перевірити власний зафіксований read/staging seam.

Accepted reference sources передаються byte-exact. Пакет не підтверджує нову встановлену базу. Впровадження після незалежного review: backup дозволених paths → перевірка restore → additive merge лише own file → ті ж baseline/component на exact installed bytes → незалежне installed review. Rollback тільки own accepted hash; чужі зміни не видаляти. Будь-який SQL/provider/restart потребує окремого конкретного плану, тут не передбачений.
