# Web Client `uk` locale patches

These patches are intentionally small and upstream-oriented. They add the
`uk` descriptor to the current Carbonio Shell UI registry, register the
`date-fns` Ukrainian locale, and add the language-selector labels to the shell
i18n catalog.

## Pinned bases

- `carbonio-shell-ui`: `97bfc56fb044760cc0c36ce0542974638e9c9c4b`
  (`15.3.12`, checked 2026-10-06)
- `carbonio-shell-ui-i18n`: `e462a874c5594b4ecad2fe1a74ed84f7c9231858`
  (checked 2026-10-08)

Apply `0001` to the Shell UI source and `0002` to the matching shell i18n
repository. Do not apply these patches to generated `/opt/zextras` files.

## Update procedure

1. Fetch the next upstream release and record its commit SHA.
2. Apply the patches with `git apply --check` first.
3. Resolve only context drift around the locale tables; do not overwrite
   unrelated upstream changes.
4. Run TypeScript checks, the upstream test suite, and the official package
   build (`pnpm run build:pkg`).
5. Verify the generated `component.json` commit path and package ownership
   before any deployment.

If upstream adds `uk` itself, drop the corresponding hunk and retain only the
missing pieces. A patch conflict is a required review gate, not a reason to
edit production in place.
