# Updating after Carbonio release

Безопасный pre-translation workflow:

```bash
python -m carbonio_uk discovery
python -m carbonio_uk fetch
python -m carbonio_uk audit
python -m carbonio_uk validate
python -m carbonio_uk glossary
python -m carbonio_uk translate --dry-run --provider mock
```

English задаёт обязательные leaf-ключи, существующие непустые UK значения
сохраняются, RU используется только как reference. Fetch привязан к commit SHA
из manifest и пишет только в `.cache/upstream/`. Validator должен выполняться
до любого перевода; non-zero означает, что baseline содержит critical issues.

Dry-run показывает missing/empty keys, число batches, объём English source и
целевые файлы, но не вызывает provider и ничего не переводит. После review
следует отдельно принять решение о разрешении реального EN → UK перевода.

## Controlled mock rehearsal

После ручного review разрешён offline mock rehearsal. `review apply` создаёт
approval sidecar, но сам перевод не меняет. `merge --review-approved` является
вторым обязательным gate и создаёт только staging output. Batch checkpoints
находятся в `.cache/checkpoints/`, content-addressed ответы mock provider — в
`.cache/translation/`. Повторный запуск должен завершаться cache hits без новых
provider calls.

Частичный `--limit` предназначен для QA pipeline: validator ожидаемо оставляет
необработанные ключи missing. Такой staging result не готов к deployment.

Новый Admin Console остаётся `active/blocked`: packaging aggregator
`carbonio-webui-i18n` включает legacy `carbonio-admin-ui-i18n`, но не содержит
подтверждённый публичный источник переводов `carbonio-admin-console-ui`.

## Controlled real pilot

`python -m carbonio_uk pilot` создаёт только preview 10 Login + 10 Mail и не
вызывает API. После ручной проверки плана execution требует одновременно
`--provider openai --execute --model MODEL`. Каждый результат остаётся в
`review/pending/`, проходит placeholder/markup validation и требует отдельного
`review decide --decision approve|reject`. Подробности и safety gates описаны в
[`real-translation-pilot.md`](real-translation-pilot.md).
