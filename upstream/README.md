# Upstream submission set

This directory describes the changes that can be submitted upstream. It does
not contain credentials, production snapshots, or generated deployment files.

## Translation pull requests

Submit one pull request per i18n repository. Copy only the matching catalog
from `translations/uk/<component>/` into that repository and validate it
against the pinned English catalog in `manifest.yaml`. Do not combine catalogs
from different repositories in one pull request.

The exact repository, file, and audit commit for every pull request are listed
in [`pr-plan.yaml`](pr-plan.yaml). Twelve keys with empty English source
values are intentionally excluded from the submission set.

## Functional Shell pull request

Submit `patches/shell/0001-carbonio-shell-ui-add-uk-locale.patch` to
`carbonio-shell-ui`. Submit the matching label catalog change
`patches/shell/0002-carbonio-shell-ui-i18n-add-uk-label.patch` separately to
`carbonio-shell-ui-i18n`.

The functional patch is required because a locale file alone does not register
`uk` in the language selector or load `date-fns/locale/uk`.

## Validation before opening a PR

```bash
python3 -m carbonio_uk audit --uk-root translations/uk --strict
python3 -m carbonio_uk validate --uk-root translations/uk
python3 -m unittest discover -s tests -v
```

The staged catalogs currently have twelve deliberate source gaps. The former
interpolation-spacing warnings and Auth UI markup mismatch have been resolved
in the staged catalogs and covered by the validator.

## What is not ready

- `carbonio-admin-console-ui` has no confirmed public i18n repository in the
  current discovery and therefore has no translation PR here.
- The twelve empty-English keys have no reliable source-of-truth value; they
  are not silently invented.
- Package-manager publication and deployment are outside these upstream PRs.
