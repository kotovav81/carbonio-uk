# Request to review and ship Ukrainian localization

Hello Zextras maintainers,

I am Котов Андрій (@kotovav81). I would like to contribute our Ukrainian (`uk`)
localization and ask you to include the reviewed translations and Ukrainian
language selection in official Carbonio releases.

Prepared translations are submitted as separate catalog-only pull requests:

- Shell: https://github.com/zextras/carbonio-shell-ui-i18n/pull/31
- Mail: https://github.com/zextras/carbonio-mails-ui-i18n/pull/40
- Calendar: https://github.com/zextras/carbonio-calendars-ui-i18n/pull/36
- Contacts: https://github.com/zextras/carbonio-contacts-ui-i18n/pull/43
- Files: https://github.com/zextras/carbonio-files-ui-i18n/pull/37
- User Login: https://github.com/zextras/carbonio-login-ui-i18n/pull/29
- Admin Login: https://github.com/zextras/carbonio-admin-login-ui-i18n/pull/30
- Auth UI: https://github.com/zextras/carbonio-auth-ui-i18n/pull/34
- Tasks: https://github.com/zextras/carbonio-tasks-ui-i18n/pull/29
- Workstream Collaboration: https://github.com/zextras/carbonio-ws-collaboration-ui-i18n/pull/33
- Selector label EN/UK: https://github.com/zextras/carbonio-shell-ui-i18n/pull/32

English is the source of truth, existing Ukrainian translations are preserved
except explicit reviewed corrections, and placeholders/markup are validated.
This is AI-assisted EN → UK work with manual review, not a claim of complete
independent linguistic review. Feedback and terminology corrections are welcome.

Ukrainian registration in carbonio-shell-ui and date-fns locale loading are
prepared separately with two tests against fresh upstream
`d83b55624ee4c3cc081b7f9fdfaf7ca36a65f416`. TypeScript, targeted ESLint, tests,
package and library builds pass. Full upstream test-suite execution and live
deployment of this exact new revision are not claimed.
The functional patch is published at:
https://github.com/kotovav81/carbonio-uk/blob/main/patches/shell/0003-current-upstream-uk-locale-with-tests.patch

GitHub currently rejects further fork creation with “was submitted too quickly”.
The functional Shell PR and Storages translation PR (29 values) will follow
once that restriction lifts. Search and Auth properties have no proposed diff.

Known gaps: twelve untranslated keys have empty English source values; fresh
Files upstream has four additional strings. These gaps are explicitly disclosed
in component PRs; we do not claim 100% coverage. Current Admin Console's public
translation source remains unconfirmed.

Could you please:

1. Review the translation PRs and advise on the preferred translation platform
   or contribution process, if direct PRs are not appropriate.
2. Include accepted catalogs in release tags/packages consumed by this
   carbonio-webui-i18n aggregator.
3. Coordinate Ukrainian locale registration so users can select Українська.
4. Point us to the source/context for empty-English keys and the current Admin
   Console translation repository.

Project and reproducible audit tooling: https://github.com/kotovav81/carbonio-uk
Submission status: https://github.com/kotovav81/carbonio-uk/blob/main/docs/submission-2026-10-13.md

No branding, private infrastructure settings or deployment patches are requested
for upstream. An installed earlier revision has been smoke-tested by internal
users; that does not replace upstream integration testing.

Thank you!
