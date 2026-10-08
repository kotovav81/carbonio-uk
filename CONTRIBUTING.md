# Contributing

Thank you for helping improve Carbonio Ukrainian localization.

## Translation rules

- English is the structural source of truth.
- Existing Ukrainian values are preserved unless an explicit review decision approves a correction.
- Russian is reference context only; translations are produced from English to Ukrainian.
- Do not translate keys, placeholders, protocol names, or HTML tags.
- Keep JSON/properties formatting and UTF-8 encoding valid.

Before opening a pull request:

```bash
python3 -m py_compile carbonio_uk/*.py carbonio_uk/providers/*.py carbonio_uk/formats/*.py
python3 -m unittest discover -s tests -v
```

Translation changes should be submitted separately from functional Shell changes.
Do not include server snapshots, credentials, branding, or deployment-specific files.

For large language updates, open a draft pull request first and identify the
upstream component, source commit, review method, and unresolved strings.
