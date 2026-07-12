# CDX Manager 0.9.16

## Highlights

- Clear error message when a provider CLI binary is broken instead of a raw Python traceback.
- Profile disk usage, cleanup candidates, explicit cleanup actions, and daily space-recovery notices.

## Changes

### Friendlier auth probe failures

Launching a session whose provider CLI exists but cannot be executed (corrupted install, wrong architecture, or a script missing its shebang — e.g. `Exec format error` on `~/.local/bin/claude`) previously crashed with an unhandled `OSError` traceback. The auth probe now catches all `OSError` failures and reports an actionable message telling the user to reinstall the provider CLI, exiting with code 126.

### Profile disk maintenance

`cdx disk` measures `CDX_HOME`, while `cdx disk profiles` adds a per-profile breakdown. `cdx disk profiles --candidates` identifies temporary marketplace/plugin staging directories and old logs with size, risk, reason, and evidence. Cleanup remains explicit through `cdx clean profiles --tmp` or `cdx clean profiles --old-logs DAYS`.

Advisory commands perform a read-only cleanup check at most once per day and warn only when documented disk or reclaimable-space thresholds are reached. Cleanup failures now stop with a non-zero error naming the affected path instead of silently reporting zero bytes removed.

The new `disk` command is reserved as a session name. Existing sessions named `profiles` remain compatible: `cdx clean profiles` still clears that session's transcripts, and profile-wide cleanup is selected only when `--tmp` or `--old-logs` is supplied.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
