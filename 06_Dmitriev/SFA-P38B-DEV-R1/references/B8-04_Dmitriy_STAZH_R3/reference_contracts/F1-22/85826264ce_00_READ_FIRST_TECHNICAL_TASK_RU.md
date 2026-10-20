# F1-22 R1 — для следующего кандидата

Реализуйте чистый компонент точной материализации уже выбранного и связанного языкового шаблона FIRST. Компонент проверяет происхождение шаблона и выдаёт буквальные subject/body для дальнейшей подготовки сообщения. Это отдельный участок R07 / FG04,FG06, приближающий пилот; закрытие FG и запуск отправок здесь не заявляются.

Проект: sales-manager-first. Статус пакета: подготовлен, независимая проверка ещё обязательна; выдача и начало работы не подтверждены. Результат включает реализацию, собственные тесты и документацию. Исполнитель пока не назначен.

## Порядок работы

1. CP0: подтвердить полученный task_id/revision, окружение, прочтение CONTRACT.json, сведения о текущих параллельных заданиях; совпадение с F1-10 определяет владелец после фактической проверки личности, оно не предполагается. Сверить CHECK_PACKAGE.py и исходный baseline.
2. Реализовать только source/sales_template_materialization.py: `materialize_bound_template(loaded_registry:dict,bound_language:dict,*,template_id:str)->dict` и `TemplateMaterializationError(ValueError)`.
3. Выполнить каждый stage CONTRACT.json буквально, в указанном порядке; ошибки с несколькими нарушениями определяются первой стадией. Не писать собственную замену F106. F120 ещё не принят: использовать прилагаемый frozen output, не импортировать отсутствующий sales_action_locale.
4. Собственные тесты source/tests/wave4/test_f122.py; новые JSON только source/tests/fixtures/wave4/f122/*.json; документация docs/F1-22_IMPLEMENTATION.md. За пределами allowlist изменения запрещены.
5. Прогнать отдельные baseline/candidate проверки, зафиксировать actual stdout, counts, exitcodes и outputs. Передать один ZIP по RETURN_RU.md; после проверки отдельный инженер внедряет.

## Контракт без выбора трактовки

Полный нормативный API, точные fieldsets и последовательность ошибок — CONTRACT.json. Полные literal inputs и expected outputs — EXAMPLES.json. Вход loaded_registry обязан быть реально полученным из F106, а не утверждением по schema_version. Полная ревалидация всех пакетов выполняется actual build_policy_language_fields. Bound template проверяется actual validate_language_pack на ephemeral одном шаблоне до бизнес-сравнений версий. Поэтому некорректный bound fact-list даёт INVALID_FACT_SET, неизвестный факт шаблона — UNAPPROVED_FACT, а корректный список bound facts вне loaded approved facts — FACT_SCOPE_MISMATCH на последней стадии.

Выход ровно schema_version,locale,language_pack_version,registry_version,kind,subject,body,fact_ids,template_id. Тексты и список фактов сохраняются точно; никакой интерполяции, перевода, trim, исполнения команд, LLM, eval, времени, I/O, SQL, внешней сети или отправок. Скобки и команды в body — буквальные символы. INITIAL требует непустую тему; остальные виды могут иметь пустую subject. Требования фактов и дубликатов принадлежат F106.

Не добавлять qa_verified, approved, grant, external_effect_authorized, release_mode. Материализация не доказывает качество языка или персонализации. Синтетические EN/RU пакеты включают INITIAL/QUESTION/OBJECTION/FOLLOWUP/HANDOFF; de-DE показывает generic core и не означает опубликованную поддержку языка. Все inputs/ неизменяемы и находятся вне source/.

## Приёмка

Все 11 позитивных golden inputs EXAMPLES.json; отрицательные коды; все пять kind EN/RU; третий язык; пустая INITIAL subject; неверные kind/locale/fact_ids; extras; изменённые version/registry; другой id с тем же kind; изменённые whitespace/fact ordering; неправильный чужой pack; multiple-error priority. Проверить полный exact result, стабильный replay, deep immutability в обе стороны и отсутствие побочных эффектов. Обязательны no-skip собственные тесты и регрессия accepted F106 44 tests. Baseline 204 не является приёмкой нового компонента.

## Граница внедрения

Передача F120 bound + F106 actually loaded registry + сохранённый selected template_id → F122 → отображение subject/body в точный F114 payload. Не повторять решение binding_config/now или выбор locale/template; не изменять F105/F106/F114/F120/Camel. HANDOFF текст никогда не заменяет полный контекст F119/F109. QA facts/source/contact/materials остаются обязательны. В sales_preparation_contract текущий whitelist не включает ru-RU: это отдельный residual интегратора, чужой файл здесь не исправлять. До accepted F120 return production import запрещён. Реальные продуктовые wording/facts и публикация packs — будущая настройка пилота.
