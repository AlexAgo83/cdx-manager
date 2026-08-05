# CDX Manager 0.12.4

## Highlights

- `cdx import --force` now preserves local Codex plugins when refreshing from bundles that do not include plugin files.

## Changes

### Force import plugin preservation

Force imports of auth-bearing bundles keep detected local `plugins/` state instead of deleting it when the incoming bundle omits plugin files. This keeps locally installed Codex plugins available after credential refresh imports.

## Validation

- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
