# Deployment

Production deployment пока не выполняется. После discovery документировать
официальный package/build путь, backup, ownership, reload, cache и rollback.
Ручное редактирование `/opt/zextras` допускается только для диагностики.
## Live Web Client `uk` registry overlay

The supported deployment path is package-based and pinned to the installed
Shell UI commit. Do not copy minified files into `/opt/zextras` manually.

The current test deployment uses:

- `carbonio-shell-ui 15.1.0-1ubuntu+uk1` built from Shell `v15.1.0`;
- `carbonio-uk-shell-i18n 1.0.0-1`, a one-file `dpkg-divert` overlay for the
  Shell `uk.json` resource.

The exact backup paths, checksums, verification and rollback commands are in
[`reports/live-uk-locale-deployment-20261008.md`](../reports/live-uk-locale-deployment-20261008.md).

The overlay package is deliberately separate from the monolithic
`carbonio-webui-i18n` package because the latter contains paths also owned by
component packages. `dpkg-divert` keeps the upstream file as
`uk.json.distrib`, so a future package update does not silently erase the
active translation. After each update, rebuild the overlay from the new
upstream catalog and rerun validation.
