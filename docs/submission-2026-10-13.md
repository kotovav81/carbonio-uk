# Ukrainian upstream submission — 2026-10-13

Contributor: Котов Андрій ([@kotovav81](https://github.com/kotovav81)).
Submitted catalog-only changes against fresh upstream revisions. English is the
source; Russian is reference-only. AI-assisted candidates received manual review
and structural checks; complete independent linguistic review is not claimed.
No infrastructure, branding, credentials, or deployment artifacts are submitted.

## Open pull requests

| Component | PR |
|---|---|
| Shell translations | https://github.com/zextras/carbonio-shell-ui-i18n/pull/31 |
| Admin Login | https://github.com/zextras/carbonio-admin-login-ui-i18n/pull/30 |
| Login | https://github.com/zextras/carbonio-login-ui-i18n/pull/29 |
| Auth UI | https://github.com/zextras/carbonio-auth-ui-i18n/pull/34 |
| Mail | https://github.com/zextras/carbonio-mails-ui-i18n/pull/40 |
| Calendar | https://github.com/zextras/carbonio-calendars-ui-i18n/pull/36 |
| Contacts | https://github.com/zextras/carbonio-contacts-ui-i18n/pull/43 |
| Files | https://github.com/zextras/carbonio-files-ui-i18n/pull/37 |
| Tasks | https://github.com/zextras/carbonio-tasks-ui-i18n/pull/29 |
| Workstream Collaboration | https://github.com/zextras/carbonio-ws-collaboration-ui-i18n/pull/33 |

Shell selector label is a separate two-file PR (EN/UK):
https://github.com/zextras/carbonio-shell-ui-i18n/pull/32.

## Validation

- Project unit tests: 24 passed.
- Changed translation values: checked against fresh English for non-empty
  strings, matching placeholders and supported markup. Upstream Ukrainian
  values were compared to pinned originals before submission.
- Twelve empty-English source gaps remain documented in the translation PRs.
- Fresh Files English adds four further missing strings; Files PR explicitly
  discloses these. No 100% claim.
- Search and Auth properties have no intended changes; no empty PRs opened.

## Functional Shell registration

Fresh upstream base: `d83b55624ee4c3cc081b7f9fdfaf7ca36a65f416`.
Prepared local commit: `b91df49` (full commit available in the local checkout).
Adds uk to STATIC_LOCALES, lazy date-fns UK loading and two tests.
Pinned pnpm install, targeted Vitest (2 passed), TypeScript, targeted ESLint,
build:pkg and build:lib all passed. Webpack emitted asset-size warnings.
The full upstream test suite and live deployment of this fresh revision were
not performed.

`patches/shell/0003-current-upstream-uk-locale-with-tests.patch` is a standalone
replacement for 0001, NOT a patch to apply after 0001. It includes current tests.
Functional Shell PR and Storages translation PR are blocked by GitHub's HTTP
403 “was submitted too quickly” on fork creation. Existing PRs are open; no
claim that these two remaining PRs exist.

## Next steps

1. After GitHub allows fork creation, fork carbonio-shell-ui, push the tested
   functional commit and open its separate PR.
2. Fork carbonio-storages-ui-i18n and submit the 29 prepared UK values.
3. Ask maintainers to review/merge catalogs, accept locale registration and
   update release tags used by carbonio-webui-i18n packaging.
4. Resolve empty-English sources and new Files strings with product context.
5. Current Admin Console source remains unconfirmed; no Admin Console coverage
   or support claim is made.

Production files and services were not changed by this submission.
