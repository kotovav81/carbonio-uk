# Controlled real-translation pilot

Pilot ограничен ровно 20 missing leaf-ключами: 10 из Login и 10 из Mail.
Admin Console, production и upstream UK не входят в scope.

## Обязательный preview

```bash
python -m carbonio_uk pilot
```

Команда не вызывает provider и создаёт `reports/real-pilot-plan.yaml` и `.md`.
Для каждой строки показываются component, immutable commit SHA, full key, EN,
RU reference и совпавший glossary context. RU сохраняется только в плане для
ручного QA и не передаётся provider.

## Execution gate

Реальный вызов возможен только при одновременном указании provider, execute и
конкретной модели:

```bash
python -m carbonio_uk pilot --provider openai --execute --model MODEL
```

API key передаётся стандартным способом OpenAI SDK через environment; ключи не
записываются в manifest, reports или pending sidecars. Integration использует
Responses API и Structured Outputs:
<https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses>.

Без `--execute` команда всегда остаётся preview, даже если указан
`--provider openai`. Без `--provider openai` или explicit `--model` execution
отклоняется до создания API client.

## Pending и validation

Каждый успешный ответ немедленно записывается отдельно в
`review/pending/<component>/<row-id>.yaml`. Sidecar содержит EN, RU reference,
glossary context, model, UK candidate, placeholder/markup/non-empty validation
и status. Pending результаты не попадают в merge или upstream автоматически.

После batch создаются `reports/real-pilot-review.json` и `.md`. Повторный
execution пропускает уже существующие pending rows, используя их как per-row
checkpoint.

## Per-row decision

```bash
python -m carbonio_uk review decide \
  --component login --key FULL.KEY --decision approve --note "reviewed"

python -m carbonio_uk review decide \
  --component mail --key FULL.KEY --decision reject \
  --note "terminology needs revision"
```

Decision сохраняется в `review/decisions/`; pending sidecar остаётся
неизменным. Даже `approve` не выполняет merge автоматически.

## Admin Console

Admin Console остаётся `active/blocked`. `carbonio-webui-i18n` агрегирует
legacy `carbonio-admin-ui-i18n` и не предоставляет translation source для
нового `carbonio-admin-console-ui`.

## Offline manual fallback

Без OpenAI SDK и API key используется тот же pinned набор:

```bash
python -m carbonio_uk manual export
# заполнить uk_candidate в review/manual-pilot.yaml
python -m carbonio_uk manual import
```

Export показывает EN, RU reference, glossary context, placeholders и markup.
Import проверяет UTF-8, non-empty, точные placeholder names и markup, после
чего пишет per-row validation только в `review/pending/`. Автоматический merge
не выполняется.
