# CDX Manager 0.9.7

## Highlights

- Hardened profile cleanup so read-only provider cache files do not block session removal or repair cleanup.

## Changes

### Read-only profile cleanup

`cdx rmv`, session overwrite rollback cleanup, and repair quarantine cleanup now make profile trees user-writable before deleting them.

This fixes failures seen when provider-managed caches contain read-only files, including nested Go module cache paths created under session-specific provider homes.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
