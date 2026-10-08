# Upstream submission status

## Ready now

- Thirteen component-specific Ukrainian catalogs are staged under
  `translations/uk/`.
- Each catalog is tied to an upstream repository and commit in `manifest.yaml`
  and `upstream/pr-plan.yaml`.
- The Shell locale-selector and `date-fns/locale/uk` functional patch is
  separated from translation changes.
- The second Shell i18n label patch is separated from the functional patch.
- Existing Ukrainian values are preserved; the staged merge made zero
  overwrite attempts.
- The package overlay was reproducibly built but is not part of upstream PRs.

## Remaining before submission

1. Run the strict audit and validation against the exact current upstream
   commits immediately before opening each PR.
2. Resolve the twelve empty-English keys with upstream product context, or
   document them as intentionally absent from the English catalog.
3. Obtain reviewer confirmation for the Auth properties destination and the
   current Admin Console i18n source.
4. Apply the Shell patches to a fresh checkout and run the upstream TypeScript,
   lint, test, and package-build commands.
5. Open separate PRs, starting with Mail, Calendar, Contacts, Files, and Shell.

## Not a blocker for translation PRs

The Carbonio production overlay, local branding, live snapshots, and package
installation are deliberately excluded from upstream submissions. They require
separate deployment review and rollback procedures.

## Current claims

The project may claim “2,932 reviewed Ukrainian candidate translations across
13 active components pinned to recorded upstream commits”. It must not claim
“100% coverage” until the twelve empty-English keys are resolved or formally
accepted by upstream maintainers.
