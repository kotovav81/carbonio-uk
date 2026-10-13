# Ukrainian localization contribution — translation PRs ready for review

Hello Zextras team and Carbonio community,

My name is Котов Андрій (GitHub: @kotovav81). We have prepared an expanded
Ukrainian (`uk`) localization for Carbonio CE and would like to contribute it
to official releases. This is a contribution/review request, not a product
support incident.

Our GitHub tracking issue was automatically closed with instructions to use
this forum: https://github.com/zextras/carbonio-webui-i18n/issues/87.
The following 11 pull requests are currently open:

- Mail: https://github.com/zextras/carbonio-mails-ui-i18n/pull/40
- Calendar: https://github.com/zextras/carbonio-calendars-ui-i18n/pull/36
- Contacts: https://github.com/zextras/carbonio-contacts-ui-i18n/pull/43
- Files: https://github.com/zextras/carbonio-files-ui-i18n/pull/37
- Shell translations: https://github.com/zextras/carbonio-shell-ui-i18n/pull/31
- Ukrainian selector label: https://github.com/zextras/carbonio-shell-ui-i18n/pull/32
- User Login: https://github.com/zextras/carbonio-login-ui-i18n/pull/29
- Admin Login: https://github.com/zextras/carbonio-admin-login-ui-i18n/pull/30
- Auth UI: https://github.com/zextras/carbonio-auth-ui-i18n/pull/34
- Tasks: https://github.com/zextras/carbonio-tasks-ui-i18n/pull/29
- Workstream Collaboration: https://github.com/zextras/carbonio-ws-collaboration-ui-i18n/pull/33

English is the source of truth. Existing Ukrainian translations are preserved
except explicit reviewed corrections. New translations are AI-assisted EN → UK
with manual review; maintainer linguistic review is welcome. Changed values
have been checked for placeholders and supported markup, and our tooling has
24 passing unit tests. An earlier installed revision is being tested by
internal users, particularly in Mail and Calendar.

We do not claim 100% coverage: twelve keys have empty English source values,
and current Files upstream introduced four additional strings. These gaps
are disclosed in the PRs. Current Admin Console coverage is not claimed.

We also prepared a separate minimal Shell source patch registering `uk` in
the language selector and loading Ukrainian date-fns locale data. Against
fresh upstream, its two tests, TypeScript check, targeted ESLint, package and
library builds passed. GitHub temporarily blocked creation of the remaining
forks; the functional Shell and Storages PRs are not yet open.

Project: https://github.com/kotovav81/carbonio-uk
Submission details: https://github.com/kotovav81/carbonio-uk/blob/main/docs/submission-2026-10-13.md
Tested Shell patch: https://github.com/kotovav81/carbonio-uk/blob/main/patches/shell/0003-current-upstream-uk-locale-with-tests.patch

Could a moderator please direct this contribution to the localization and
Web Client maintainers? We would appreciate guidance on:

1. Review/acceptance of these PRs or importing them into your translation platform.
2. Including accepted translations in official localization packages/releases.
3. Enabling Українська in the Web Client language selector.
4. The correct context for empty English values and the current Admin Console
   translation source.

The translation CONTRIBUTING pages link to carbonio-ce-contribute; please
confirm the current contribution channel if that page has moved.

No branding, private URLs, credentials or production-specific changes are
included in these contributions. We are ready to help maintain the translation
and incorporate feedback.

Thank you,
Котов Андрій (@kotovav81)
