# Техническое задание: carbonio-uk

## Цель

Создать сопровождаемую украинскую локализацию Carbonio, которую можно повторно
синхронизировать с upstream после обновлений, не уничтожая существующие
переводы и не редактируя установленные файлы вручную.

## Discovery

Найти актуальные публичные repositories организации `Zextras`, связанные с
Carbonio Web Client, Admin Console, login/auth, mail, calendar, contacts,
files, search, tasks, collaboration, storage и i18n. Для каждого зафиксировать
URL, default branch, active/archived status, технологию, translation paths,
наличие EN/RU/UK, commit SHA и способ сборки. Archived/legacy компоненты не
включать автоматически; отдельно помечать `status: legacy`.

Результат:

- `reports/discovery.md`
- `reports/discovery.json`
- `manifest.yaml`

Таблица discovery: `Component | Repository | Branch | EN | RU | UK |
Translation path | Active | Included`.

## Manifest

Manifest должен описывать компонент без hardcode списка в Python:

```yaml
components:
  shell:
    repository: https://github.com/Zextras/...
    branch: main
    translation:
      type: json
      english: ...
      russian: ...
      ukrainian: ...
      locale: uk
    commit: ...
```

## Audit

Реализовать `carbonio-uk audit` и `python -m carbonio_uk audit`.
Считать leaf translation values, а не строки файла. Отчёт должен включать EN,
RU и UK counts, translated/missing/extra keys, empty/null/invalid values,
identical EN/UK, placeholder/markup/interpolation errors и suspicious leftovers.

Same-as-English разрешать по allowlist технических терминов (`API`, `DNS`,
`SMTP`, `IMAP`, `URL`, `IP` и т.п.) и по ручным исключениям.

Опции: `--json`, `--component`, `--compare-locale ru`, `--strict`.

## Merge и перевод

Default — `KEEP EXISTING UK`. Existing non-empty Ukrainian значения не менять.
Missing/empty значения добавлять в порядке English source. AI provider должен
быть абстракцией с минимумом manual/export и OpenAI implementations.
Переводчик получает component, full key, English value, glossary, placeholder
rules и UI context. Нельзя передавать RU как основной текст перевода.

`translate --dry-run` показывает missing count, batches, estimated size и
изменяемые файлы. Batch должен быть ограниченным, повторяемым и иметь
checkpoint/cache по SHA256(source + glossary-version + prompt-version).

## Validator

`carbonio-uk validate` проверяет JSON/properties syntax, duplicate keys,
missing/extra/empty values, UTF-8, placeholders, interpolation, HTML tags,
plural forms, control characters, suspicious English/Russian leftovers и
glossary consistency. Critical errors дают non-zero exit code.

Поддержать JSON и `.properties`, включая comments, escapes, Unicode и
multiline values. Не создавать бессмысленные diffs.

## Glossary и QA

Создать `glossary/uk.yaml`, сначала собрав термины из существующего UK. Список
подозрительных строк вынести в QA report: длинные значения, English leftovers,
одинаковые EN/UK, markup-heavy, placeholder-heavy и glossary conflicts.

## Web и Admin

Исследовать актуальные `carbonio-shell-ui` и `carbonio-admin-console-ui`.
Legacy `carbonio-admin-ui` использовать только для исторического сравнения.
Найти locale registry, selector, browser detection, preference storage,
fallback и загрузку resources. Если `uk` существует, но не доступен в selector,
сделать минимальный patch в `patches/shell/` или `patches/admin-console/`.

## Tests и CI

Добавить fixtures и unit tests для flattening, missing/extra, merge preservation,
allowlist, placeholders, HTML, properties, glossary, dry-run и malformed JSON.
Mock provider не обращается к AI API. GitHub Actions выполняет lint/test/audit/
validate без credentials.

## Build/deployment

Исследовать официальный pnpm/Turborepo/build/package workflow. Документировать:

- `docs/build.md` — Web Client, Admin Console, i18n;
- `docs/deployment.md` — development/production, backup, ownership, reload,
  browser cache и rollback;
- `docs/updating.md` — fetch → audit → translate → validate → report;
- `docs/upstream-contribution.md` — small commits и PR-ready patches.

Не считать ручное изменение `/opt/zextras/...` production-решением.

## Definition of done

Для компонента: missing required keys = 0, empty required UK = 0,
placeholder errors = 0, invalid JSON = 0, critical markup errors = 0.
Coverage всегда указывается против конкретного upstream commit SHA.

