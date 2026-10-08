# AGENTS.md — carbonio-uk

## Назначение

`carbonio-uk` — отдельный open-source проект для воспроизводимого аудита,
синхронизации и проверки украинской локализации Carbonio. Проект не изменяет
рабочий Carbonio напрямую и не хранит production-секреты.

## Обязательный порядок работы

1. Discovery актуальных публичных репозиториев Zextras.
2. Manifest с repository, branch, commit и путями локалей.
3. Fetch English/Russian/Ukrainian ресурсов в `.cache/upstream/`.
4. Рекурсивный audit leaf-ключей.
5. Извлечение и согласование glossary.
6. Validator до любого массового перевода.
7. Dry-run и mock translation.
8. Только затем реальный EN → UK перевод.
9. Проверка Web Client/Admin Console и минимальные upstream-friendly patches.
10. Документированный build/deployment/rollback.

## Источники истины

- English определяет набор ключей.
- Existing Ukrainian сохраняется по умолчанию.
- Russian используется только для контекста, QA и поиска подозрительных мест.
- Перевод выполняется EN → UK, а не RU → UK.

## Безопасность

- Не коммитить API keys, пароли, SSH keys, cookies и токены.
- Не редактировать `/opt/zextras` как production-метод.
- Перед deployment делать backup и фиксировать upstream commit SHA.
- Не удалять существующие украинские значения автоматически.
- Не переводить ключи, placeholders, протоколы и API identifiers.

## Проверки перед передачей

```bash
python3 -m py_compile carbonio_uk/*.py carbonio_uk/providers/*.py carbonio_uk/formats/*.py
python3 -m unittest discover -s tests -v
```

Для изменений packaging/docs дополнительно проверить, что примеры команд не
содержат реальные credentials или private paths.

