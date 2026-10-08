# Build

Общий localization package исследован на pinned
`Zextras/carbonio-webui-i18n` commit. Подробности deb/rpm, container и Jenkins
workflow, включая ограничения воспроизводимости, описаны в
[`package-workflow.md`](package-workflow.md). Лицензионные условия вынесены в
[`licensing.md`](licensing.md).

Production build и publish не выполнялись: официальный pipeline зависит от
Jenkins shared library, registry/JFrog configuration и build credentials.
