# CDX Manager 0.9.16

## Highlights

- Clear error message when a provider CLI binary is broken instead of a raw Python traceback.

## Changes

### Friendlier auth probe failures

Launching a session whose provider CLI exists but cannot be executed (corrupted install, wrong architecture, or a script missing its shebang — e.g. `Exec format error` on `~/.local/bin/claude`) previously crashed with an unhandled `OSError` traceback. The auth probe now catches all `OSError` failures and reports an actionable message telling the user to reinstall the provider CLI, exiting with code 126.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
