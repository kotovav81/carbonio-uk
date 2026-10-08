# Carbonio Ukrainian Localization

Community tooling and reviewed Ukrainian translation catalogs for the
[Zextras Carbonio](https://github.com/Zextras) web client.

The project keeps Ukrainian translations synchronized with upstream releases.
English defines catalog structure, existing Ukrainian values are preserved,
and Russian is reference context only.

## Current status

- 13 active translation components discovered and pinned by commit SHA.
- 2,924 reviewed candidate translations staged in `translations/uk/`.
- 20 ambiguous strings remain in local review and are not included here.
- 24 unit tests pass locally; CI runs on every push and pull request.
- Admin Console i18n is tracked as active/blocked until its public source is
  confirmed.
- No production files, credentials, mailbox data, or live snapshots are part
  of this repository.

## Components

The manifest covers Shell, Login, Admin Login, Auth, Mail, Calendar, Contacts,
Files, Search, Tasks, Collaboration, Storages, and Auth properties.

Translation catalogs are separate from functional patches. The Shell
locale-selector patch is in `patches/shell/` and is intended for a separate
upstream pull request.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
python -m carbonio_uk --help
```

## Workflow

```bash
python -m carbonio_uk discovery
python -m carbonio_uk fetch
python -m carbonio_uk audit --json
python -m carbonio_uk validate
python -m carbonio_uk glossary
python -m carbonio_uk translate --dry-run --provider mock
python -m carbonio_uk report
```

The default workflow is read-only until an explicit merge/review command is
used. Existing Ukrainian translations are never overwritten implicitly.
OpenAI support is optional, disabled by default, and requires an explicit
execution flag. CI never calls an AI provider.

## Repository layout

```text
carbonio_uk/       audit, fetch, merge, validation, review and CLI code
translations/uk/   reviewed Ukrainian catalogs by component
glossary/          approved Ukrainian terminology
patches/           separate functional locale-selector patch
tests/             offline unit tests and fixtures
docs/              architecture, build, deployment and contribution notes
```

Generated caches, live snapshots, review workbooks, reports, and package
artifacts are intentionally ignored by Git.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes. Translation
pull requests should target one upstream i18n repository at a time and include
the upstream commit used for the audit. Do not include branding, private URLs,
production paths, credentials, or deployment-specific changes.

```bash
python3 -m py_compile carbonio_uk/*.py carbonio_uk/providers/*.py carbonio_uk/formats/*.py
python3 -m unittest discover -s tests -v
```

The project is licensed under AGPL-3.0-only. See [LICENSE](LICENSE).
