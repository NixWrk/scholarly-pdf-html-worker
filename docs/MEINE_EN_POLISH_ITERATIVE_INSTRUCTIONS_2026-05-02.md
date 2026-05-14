# Meine EN Polish Iterative Instructions

Дата фиксации: 2026-05-02.

Это рабочая инструкция для Codex при продолжении отладки `pdf -> en raw html -> en polish html` на статьях из meine.

## Главный принцип

Работать итеративно: одна статья за раз.

Не чинить итоговый HTML вручную. Исправления должны попадать в код polish/audit/raw diagnostics так, чтобы следующий прогон сам давал лучший результат.

## Цикл одной статьи

1. Найти статью и открыть три источника:
   - исходный PDF;
   - `01.en.raw.html`;
   - `02.en.polish.html`.
2. Определить первый слой, где возникает дефект:
   - уже в PDF/OCR/text layer;
   - в raw после Marker;
   - только после EN polish.
3. Если дефект уже есть в raw, не называть его polish-регрессией. Отдельно отметить, может ли polish безопасно компенсировать его.
4. Если дефект появляется только в polish, искать причину в `src/zoteropdf2md/single_file_html.py` и связанных тестах.
5. Все наблюдения сначала занести в review/fix-plan документы, затем группировать по общим паттернам.
6. Код менять только после классификации проблемы и только если решение универсальное.

## Куда писать наблюдения

Основные документы:

- `docs/MEINE_EN_POLISH_MANUAL_REVIEW_2026-04-30.md`
- `docs/MEINE_EN_POLISH_FIX_AND_TEST_PLAN_2026-04-30.md`

Для каждой статьи фиксировать:

- `Manual Notes From User`;
- `Verification Notes`;
- `Verified Symptoms`;
- `First Broken Stage`;
- `Root Cause Hypotheses`;
- `Universal Pattern`;
- `Fix Requirements`;
- `Regression Coverage Needed`;
- `After Fix Verification`.

## Как выбирать исправления

Исправление должно быть:

- универсальным, а не привязанным к одной статье;
- guarded/context-aware;
- безопасным для типичных 7 статей;
- проверяемым тестом;
- обратимым по смыслу: если уверенности мало, лучше audit warning, чем агрессивная правка текста.

Не делать автоматическую правку, если:

- требуется восстановить большой кусок текста из догадок;
- дефект вызван отсутствующей картинкой, которой Marker не извлек;
- OCR-слой разрушил пробелы массово и локальный regex может повредить нормальный текст;
- документ помечен OCR-маркером и должен идти через будущий отдельный OCR polish sketch.

## OCR-документы

PDF с OCR-маркером в имени, например `[OCR].pdf` или `[OCR test 2026-05-01].pdf`, не считать строгим валидатором обычного EN polish.

Для них в будущем должен быть отдельный OCR polish sketch со своей политикой. Обычный EN polish может только диагностировать и осторожно компенсировать локальные дефекты, но не обязан "идеально" лечить OCR-шум.

## Минимальные команды проверки

После изменения кода запускать точечные тесты:

```powershell
python -m pytest tests\test_single_file_html.py tests\test_audit_en_polish.py -q
```

Если затронут language gate:

```powershell
python -m pytest tests\test_language_detect.py tests\test_zotero_library_single_loop_language_gate.py -q
```

Пересобрать polish для проверяемых статей:

```powershell
python scripts\repolish_en_from_raw.py --roots <article-root-1> <article-root-2> --out-report <report.json>
```

Запустить pair audit:

```powershell
python scripts\audit_en_polish.py --roots <article-root-1> <article-root-2> --pdf-diagnostics --out <audit.json>
```

При подозрении на raw-дефект:

```powershell
python scripts\audit_en_raw.py --roots <article-root> --out <raw-audit.json>
```

При подозрении на язык:

```powershell
python scripts\audit_source_language.py --roots <article-root> --out <language-audit.json>
```

## Регрессия

После каждой meaningful code change проверять:

1. статью, ради которой сделано исправление;
2. соседние meine-статьи с похожим паттерном;
3. типичные 7 статей из прежнего набора, чтобы не сломать уже стабилизированный baseline.

Если новая правка лечит одну статью, но ухудшает типичные 7, правку сузить или заменить audit-warning.

## Definition of Done для одной итерации

Итерация считается завершенной, когда:

- симптом пользователя воспроизведен или явно признан невоспроизводимым;
- первый сломанный слой определен;
- наблюдение записано в документацию;
- если правился код, добавлен или обновлен тест;
- выполнен repolish;
- выполнен audit;
- результат просмотрен вручную;
- итоговая оценка записана: что исправлено, что осталось, что переносится в будущие workstream'ы.

## Важные ограничения

- Не писать HTML обратно в Zotero без прямого запроса.
- Не редактировать generated HTML как источник истины.
- Не смешивать проблемы OCR/raw extraction с regressions EN polish.
- Не коммитить чужие несвязанные изменения.
- Если рабочее дерево грязное, трогать только файлы, относящиеся к текущей итерации.
