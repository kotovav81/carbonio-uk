# Carbonio Web UI localization package workflow

Исследован `Zextras/carbonio-webui-i18n` commit
`677d46d40c10c483f5ae2391761e6438b1adf6c6`, tag `v1.0.18`. Это aggregator:
он не хранит locale JSON в своём дереве, а собирает их из 13 i18n repositories.

## Содержимое репозитория

- `package/PKGBUILD` — описание общего deb/rpm package, version `1.0.18`;
- `Dockerfile` — multi-stage container build;
- `Jenkinsfile` — CI security scan, container publish, deb/rpm build/upload и
  semantic release;
- `yap.json` — build project `package`, artifacts output;
- `.releaserc.json` — conventional commits, version bump в PKGBUILD,
  changelog, GitHub release;
- `LICENSE.md` — AGPL v3;
- отдельного `scripts/` и локальных `.sh`, `.py` или `.js` build scripts нет.

## Package path

`package/PKGBUILD` получает 13 repositories по release tags. На исследованном
commit используются tags `v1.0.3`–`v1.0.6`, а `sha256sums` для всех git sources
установлены в `SKIP`. Функция `package()` устанавливает все `*.json`:

| Source | Destination |
|---|---|
| admin login | `/opt/zextras/admin/login-i18n` |
| legacy admin UI | `/opt/zextras/admin/iris/i18n` |
| user login | `/opt/zextras/web/login-i18n` |
| auth/calendar/contacts/files/mail/search/shell/storages/tasks/collaboration | `/opt/zextras/web/iris/<component>/i18n` |

Tags дают более стабильный input, чем moving branches, но `SKIP` checksums
ослабляют проверку содержимого. Для воспроизводимого аудита следует разрешить
каждый tag в commit SHA и сохранить это соответствие рядом с artifact metadata.

## Container path

Dockerfile использует `alpine/git:v2.54.0`, BuildKit SSH secret и выполняет
shallow clone тех же 13 repositories без tag или commit. Затем JSON копируются
в `/opt/zextras` и переносятся в финальный `alpine:3.24.2` image.

Этот путь не полностью воспроизводим: результат зависит от HEAD каждого
репозитория во время build. SSH key и dynamically generated `ssh-keyscan`
используются только во время builder stage, однако build требует корректной
секретной инфраструктуры. `carbonio-uk` не должен копировать этот credential
workflow и не хранит ключи.

## Jenkins workflow

Pipeline загружает private/shared Jenkins library `jenkins-lib-common@v4.14.2`
и использует configured credentials. Последовательность:

1. checkout и git metadata;
2. semantic-release guard;
3. gitleaks security scan;
4. multi-architecture container publish (`amd64`, `arm64`);
5. deb/rpm build для Rocky и Ubuntu;
6. upload через JFrog CLI;
7. semantic release.

Локально эту pipeline нельзя считать полностью воспроизводимой без Jenkins
shared library, registry, JFrog и signing/upload configuration. Эти внешние
операции не выполнялись.

## Важный Admin Console gap

Оба packaging paths всё ещё используют `carbonio-admin-ui-i18n`, связанный с
архивным `carbonio-admin-ui`. Актуальный `carbonio-admin-console-ui` указывает
на недоступный публично `carbonio-admin-manage-ui-i18n`. Поэтому aggregator не
разблокирует baseline-аудит нового Admin Console и не является подтверждённым
источником его переводов.

## Рекомендуемый upstream-friendly порядок

1. Зафиксировать aggregator SHA/tag и SHA всех 13 inputs.
2. Выполнить `fetch → audit → validate` на этих exact inputs.
3. Согласовать review queue и glossary conflicts.
4. Подготовить locale changes отдельными малыми commits в соответствующих
   i18n repositories.
5. Обновить tags в PKGBUILD и проверить assembled filesystem tree.
6. Только в официальной CI выполнить deb/rpm/container build, security scan и
   publish.

Ручное изменение `/opt/zextras` не является package workflow. Deployment,
backup и rollback остаются отдельным этапом после успешной сборки и проверки
artifact.

## Локальный staging overlay

После review и staged merge можно собрать детерминированный tar без обращения
к package manager, службам или `/opt/zextras`:

```bash
python -m carbonio_uk package-overlay \
  --merged-root translations/uk \
  --snapshot translations/live-carbonio-20261008 \
  --output-dir artifacts/package-staging-2924 \
  --report reports/package-staging-2924.json
```

В payload включаются только JSON-пути, которые подтверждены одновременно
upstream aggregator workflow и live snapshot. `auth_properties` валидируется,
но не включается: в snapshot нет подтверждённого destination, а aggregator
собирает JSON resources. Архив имеет нормализованные uid/gid, mode, mtime и
порядок файлов; повторная сборка одинаковых inputs должна давать тот же SHA-256.

Перед будущей установкой необходимо определить owning deb/rpm packages,
зафиксировать их версии и сделать проверяемый backup ровно затрагиваемых
UK-файлов вне `/opt/zextras`. Установка и rollback должны выполняться отдельным
одобренным package workflow, а не ручным копированием overlay.
