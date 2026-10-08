# carbonio-uk

Воспроизводимый проект украинской локализации Zextras Carbonio.

Проект сравнивает English/Russian/Ukrainian каталоги, сохраняет существующие
качественные украинские переводы, находит новые английские ключи после релизов
и готовит проверяемые upstream-friendly изменения.

## Принцип

`EN` — source of truth для структуры. `UK` — source of truth для уже готовых
переводов. `RU` — справочный язык для QA и контекста, но не источник перевода.

## Статус

Реализованы discovery, pinned fetch, recursive leaf-key audit, validator,
glossary extraction, `KEEP EXISTING UK` merge, controlled mock pipeline и
20-строчный controlled real-pilot preview.

Текущий baseline:

- 13 audit-ready components;
- Admin Console — `active/blocked`, публичный i18n source не подтверждён;
- 2944 missing/empty UK values;
- 19 unit tests проходят;
- реальный AI pilot не запускался.

## Быстрый старт

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python -m carbonio_uk --help
python -m carbonio_uk audit --help
python -m carbonio_uk validate --help
python -m carbonio_uk pilot --help
```

Полный workflow после реализации команд:

```bash
python -m carbonio_uk discovery
python -m carbonio_uk fetch
python -m carbonio_uk audit --json
python -m carbonio_uk validate
python -m carbonio_uk glossary
python -m carbonio_uk translate --dry-run --provider mock
python -m carbonio_uk report
```

Текущий безопасный workflow заканчивается на `translate --dry-run`: discovery
фиксирует репозитории и commit SHA, fetch загружает ресурсы в
`.cache/upstream/`, audit рекурсивно сравнивает leaf-ключи, validate проверяет
структуру и placeholders, glossary извлекает кандидаты из существующего UK, а
dry-run только строит план. Политика merge — `KEEP EXISTING UK`. Без
`--dry-run` в обычном translation workflow разрешён только явно выбранный
offline provider `mock`; OpenAI доступен исключительно через отдельный gated
pilot.

Controlled mock pipeline после review выполняется только явно:

```bash
python -m carbonio_uk review apply --component auth_ui --key instruction.changePassword
python -m carbonio_uk translate --provider mock --component login --limit 15 --batch-size 5
python -m carbonio_uk merge --component login --review-approved
python -m carbonio_uk validate --component login --uk-root translations/merged
python -m carbonio_uk report
```

Mock batches имеют content-addressed cache и checkpoint. Merge всегда пишет в
`translations/merged/`; cached upstream UK не перезаписывается. Review sidecar
может заменить существующий UK только после `review apply` и при явном флаге
`merge --review-approved`. OpenAI provider в mock pipeline не используется.

Подготовленный real-translation pilot описан в
[`docs/real-translation-pilot.md`](docs/real-translation-pilot.md). Команда
`python -m carbonio_uk pilot` только формирует preview 10 Login + 10 Mail.
OpenAI execution требует одновременно `--provider openai --execute` и explicit
`--model`; результаты сохраняются только в `review/pending/`.

Перед любым решением нужно просмотреть 20 строк:

```bash
python -m carbonio_uk pilot
less reports/real-pilot-plan.md
```

После явно разрешённого pilot каждая строка решается отдельно:

```bash
python -m carbonio_uk review decide \
  --component login \
  --key FULL.KEY \
  --decision approve \
  --note "reviewed"

python -m carbonio_uk review decide \
  --component mail \
  --key FULL.KEY \
  --decision reject \
  --note "needs revision"
```

Approve/reject создаёт decision sidecar и не выполняет автоматический merge.

Если OpenAI API недоступен, тот же набор из 20 строк экспортируется для
ручного заполнения:

```bash
python -m carbonio_uk manual export
# заполнить только uk_candidate в review/manual-pilot.yaml
python -m carbonio_uk manual import
```

Import проверяет UTF-8, non-empty, точные placeholder names и markup. Результаты
попадают только в `review/pending/`; automatic merge отключён.

Полный offline TSV для передачи во внешний review-проект содержит все текущие
missing/empty/null UK leaf-значения:

```bash
python -m carbonio_uk manual export --output review/manual-pilot.tsv
# заполнить только колонку UK candidate
python -m carbonio_uk manual import --source review/manual-pilot.tsv
```

Колонки `placeholders` и `markup` нельзя редактировать: import сверяет их с EN,
затем проверяет UTF-8, non-empty, placeholders и markup каждой строки. Импорт
создаёт только `review/pending/` и validation report; merge не запускается.

Проверенный полный TSV можно объединить только в отдельный staging overlay с
политикой `KEEP EXISTING UK`:

```bash
python -m carbonio_uk stage-tsv \
  --source review/2924/manual-pilot-complete-uk.tsv \
  --review review/2924/manual-review-complete.tsv \
  --output-root translations/merged-2924 \
  --report reports/staged-merge-2924.json
```

Команда сверяет TSV с pinned EN/RU, валидирует каждый непустой кандидат,
исключает review-строки, не перезаписывает непустой existing UK и автоматически
создаёт post-merge audit/validation reports. Это staging, не deployment.

Live evidence snapshot сравнивается с pinned upstream без изменения снимка:

```bash
python -m carbonio_uk live-compare \
  --snapshot translations/live-carbonio-20261008
```

Сводка записывается в `reports/live-vs-upstream.md`, а полный перечень
missing/extra/changed leaf-ключей — в `reports/live-vs-upstream.json`.
Legacy `opt/zextras/admin/iris` не считается новой Admin Console; новая Admin
Console остаётся `active/blocked` из-за отсутствия публичного i18n-источника.

## Ограничения

AI-перевод не запускается автоматически и не является обязательным для CI.
Production deployment выполняется только через package/build workflow после
backup и проверки rollback.
