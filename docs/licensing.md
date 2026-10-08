# Licensing

Проверено для публичного репозитория
[`Zextras/carbonio-webui-i18n`](https://github.com/zextras/carbonio-webui-i18n)
на commit `677d46d40c10c483f5ae2391761e6438b1adf6c6` (`v1.0.18`).

## Подтверждённая лицензия

- `LICENSE.md` содержит полный текст GNU Affero General Public License,
  version 3, 19 November 2007.
- `package/PKGBUILD` декларирует `AGPL-3.0-only`.
- README также называет GNU AGPL v3.0, хотя его ссылка указывает на
  `COPYING`, а фактический файл в репозитории называется `LICENSE.md`.

Для изменений packaging, translation resources или build scripts следует
сохранять copyright/license notices и распространять соответствующий исходный
код на условиях AGPL-3.0-only. При распространении собранных deb/rpm или
container artifacts необходимо сохранять доступ к Corresponding Source и тексту
лицензии. Для модифицированной версии, доступной пользователям по сети, следует
отдельно проверить обязательства AGPL section 13.

Это техническая фиксация лицензии upstream, а не юридическая консультация.
Перед внешним распространением продукта или изменением лицензионной модели
нужна проверка ответственным за open-source compliance.

## Границы анализа

Aggregator забирает JSON из 13 отдельных i18n-репозиториев. Перед публикацией
собственного общего пакета их license files и notices также должны быть
зафиксированы на тех же tags/commits, которые реально вошли в artifact. Наличие
лицензии aggregator не заменяет provenance каждого включённого ресурса.

`carbonio-uk` не копирует upstream license text или package artifacts в рабочие
translation outputs и не публикует их автоматически.
