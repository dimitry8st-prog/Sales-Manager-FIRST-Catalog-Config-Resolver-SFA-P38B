# F1-20 — Привязка языковой версии к действию

Исполнитель: **Александр Гуляев 1 уровень**. Проект: **sales-manager-first / Autonomous Sales Manager FIRST**.
Техническая ревизия: R1; передача: R1. Пакет подготовлен для ручной передачи владельцем. Первоначальная выдача разработчику: не подтверждена. Получение и начало: не подтверждены. Доработка не выдавалась.

## 1. Что нужно сдать

Реализовать привязка языковой версии к действию по точному API ниже, добавить собственные положительные и отрицательные тесты и подготовить воспроизводимый возврат. Результат должен работать на входах из EXAMPLES.json и обеспечивать критерии раздела5. Работа относится к FG01, FG04, FG06 и будет соединена с общей системой отдельным инженером.

FIRST — одна активная настраиваемая кампания/предложение и один ящик, первоначально EN/RU с расширяемыми версиями языковых пакетов. Обычная переписка в принятом будущем контуре автономна; неопределённые/запрещённые действия блокируются. Настоящие бизнес-данные и доступы не требуются для этой разработки.

## 2. Исходная база и зависимости

Полная identity текущей SOURCE: `0176e66cfd4d95d5980188b0d9adb0d5cfb5cc9946c3400be66e06ce69f494c5`. В source/ находятся56 безопасных необходимых файлов, включая принятые компоненты, SQL, тесты и synthetic fixtures. Их точные SHA256 заданы неизменным SOURCE_SNAPSHOT_MANIFEST.json. Все старые файлы остаются неизменными.

- `source/sales_language_registry.py` — принятая неизменная реализация/контекст.
- `source/sales_first_binding.py` — принятая неизменная реализация/контекст.

SHARED_CONTRACTS.json фиксирует общие структуры, типы, версии и правила. CONTRACT.json фиксирует ваш API; EXAMPLES.json — буквальные входы и ожидаемые результаты. Для новых зависимостей используются явные injected protocols и синтетические test doubles строго по опубликованному контракту. Они не заменяют будущую совместную приёмку настоящих реализаций. Уже выданные F1-02, F1-03, F1-10 не переписываются.

## 3. Разрешённые файлы

Пути относительно корня этого пакета:
- `source/sales_action_locale.py`
- `source/tests/wave3/test_f120.py`
- `source/tests/fixtures/wave3/f120/*.json`

Новые документы и логи возврата разрешены вне source/. Не редактировать основной runtime, чужие файлы, исходные migrations, manifests, source dependencies или runners. У каждого нового участка один владелец. Общие runtime/Make/DB изменения делает один отдельный инженер после приёмки возвратов.

## 4. Точный программный контракт

### `bind_action_locale(loaded_registry: dict, binding_config: dict, *, now: datetime, locale: str, required_template_id: str, pinned_pack_version: str|None) -> dict`

Вход: Accepted F106 loaded registry; accepted F105 config input (call validator using explicit now:datetime, never pass F105 augmented output into raw validator); locale,required_template_id,pinned_pack_version; exact pack/template shape copied from F106 source. Match binding.language_pack_versions and loaded registry versions; approved fact subset.

Выход:
```json
"{schema_version:FIRST_ACTION_LANGUAGE_V1,status:BOUND,locale:str,language_pack_version:str,registry_version:str,approved_template:dict,approved_fact_ids:list[str]}"
```
Ошибки: INVALID_INPUT, F106 LanguageRegistryError codes propagated, BINDING_LANGUAGE_MISMATCH, PACK_VERSION_CHANGED, TEMPLATE_NOT_APPROVED, FACT_SCOPE_MISMATCH.


Нормативные типы, наборы полей, порядок проверок, коды отказов и состояния содержатся в CONTRACT.json и SHARED_CONTRACTS.json. JSON-примеры времени преобразуются в aware datetime там, где API требует datetime. Поля явно перечисленных структур обязательны; неизвестные запрещены, если конкретный существующий контракт не допускает их. Не усекать ID или историю. Не выдавать строковый marker за проверенные права. В чистых функциях входы не меняются, I/O и скрытые часы/окружение отсутствуют; время передаётся явно. PG-операции выполняются только в собственной одноразовой базе и подтверждают успех после commit.

## 5. Обязательная проверка

1. EN/RU positive
2. third fixture locale without core change
3. pinned version drift reject
4. binding/registry version mismatch
5. fact outside binding reject
6. missing approved template
7. source input immutable
8. no grant extension

Реальные вызовы своей реализации обязательны; mock самой проверяемой функции запрещён. Synthetic adapters допускаются на внешних границах по точному ABI. Для PG-задач mock не подтверждает транзакции: нужны реальные два соединения, конкуренция, ошибки commit, перезапуск и восстановление. Проверки содержат assertions ожидаемых результатов и отсутствия запрещённых изменений, а не только количество пройденных тестов.

Из корня пакета:
```
python -B CHECK_PACKAGE.py
python -B run_checks.py --source source --output evidence/before
python -B run_checks.py --source source --candidate f120 --output evidence/after
```
Сначала прочитать ENVIRONMENT_AND_CHECKS_RU.md. Исходная база была проверена на Python3.12.14/psycopg3.2.9:204 компонентных теста успешны; raw logs в baseline_evidence/. Это не результат ещё отсутствующей новой реализации. До добавления собственных tests candidate-режим должен сообщать отсутствие реализации, а не PASS. Полная root-регрессия и live-процесс здесь не запускаются.

## 6. Подключение в общую систему

Производители/потребители и конкретные места будущего соединения:
- `sales_manager.process_prepare`
- `sales_manager.process_send`
- `sales_manager.process_task`

Integrator invokes build_policy_language_fields and crosschecks actual loaded pack versus F105 version map; persists selected version into action/intent and maps approved template fields to Camel frozen policy without changing Camel API.

Кандидат сдаёт новый компонент и INTEGRATION_NOTE.txt с точным порядком вызовов, зависимостями и примером. Инженер внедрения отвечает за последовательное соединение с настоящими accepted dependencies, миграции/сохранность данных, исправление общего call-site и integrated positive/fault tests. Подключение, runtime identity и полнота соответствующего FG проверяются отдельно; установка ещё одного файла без caller не считается подключением функции.

## 7. Вне вашего задания

- No registry rewrite
- No new selling-language quality claim
- No Make prompt edit

Не запускать приложение/worker, не обращаться к настоящим Make/mailbox/клиентам и не применять миграции к рабочей БД. NO_OUTBOUND в исходной базе сохраняется. Разработка eligibility/intent в synthetic tests не выдаёт live grant. Реальные права на действия и разрешённый пилот — отдельный этап владельца.

## 8. Порядок выполнения и сдачи

Сначала проверить среду, исходные хеши и совместимость контракта. Затем записать собственную матрицу проверок, реализовать только свой allowlist, выполнить обязательные tests и подготовить возврат по RETURN_RU.md. При конфликте версий/файлов/схемы остановить затронутую правку и сообщить координатору конкретный вход, ожидаемое и фактическое поведение. Не изменять общий контракт молча.

Приёмка компонента: полный контракт, все относящиеся tests, неизменный baseline, доказательный возврат и отдельная проверка. Runtime-подключение и приёмка продукта не подменяются этим результатом. После возврата и каждого внедрения координатор выдаёт владельцу отчёт о принятом объёме, изменении FIRST_INDEX_V1, оставшихся работах и следующем этапе.
