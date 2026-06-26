# CDX Manager 0.9.14

## Highlights

- Added `--passphrase-stdin` for auth bundle export/import flows, avoiding passphrases in child process environments.

## Changes

### Auth bundle passphrase input

`cdx export --include-auth` and `cdx import` now accept `--passphrase-stdin` as an alternative to `--passphrase-env`.

This lets non-interactive callers provide the bundle passphrase through standard input instead of storing it in an environment variable. The new flag is mutually exclusive with `--passphrase-env`, and export still requires `--include-auth` before a passphrase is accepted.

Usage strings, command help, README examples, and regression coverage were updated for the new input mode.

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
