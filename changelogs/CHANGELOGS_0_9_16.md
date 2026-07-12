# CDX Manager 0.9.16

## Highlights

- Clear error message when a provider CLI binary is broken instead of a raw Python traceback.
- Profile disk usage, cleanup candidates, explicit cleanup actions, and daily space-recovery notices.
- Visibility into banked Codex rate-limit resets in text and JSON status output.

## Changes

### Friendlier auth probe failures

Launching a session whose provider CLI exists but cannot be executed (corrupted install, wrong architecture, or a script missing its shebang — e.g. `Exec format error` on `~/.local/bin/claude`) previously crashed with an unhandled `OSError` traceback. The auth probe now catches all `OSError` failures and reports an actionable message telling the user to reinstall the provider CLI, exiting with code 126.

### Profile disk maintenance

`cdx disk` measures `CDX_HOME`, while `cdx disk profiles` adds a per-profile breakdown. `cdx disk profiles --candidates` identifies temporary marketplace/plugin staging directories and old logs with size, risk, reason, and evidence. Cleanup remains explicit through `cdx clean profiles --tmp` or `cdx clean profiles --old-logs DAYS`.

Interactive disk scans now report the current stage and profile count on stderr so long-running measurements no longer appear stalled. JSON and redirected output remain unchanged.

Advisory commands perform a read-only cleanup check at most once per day and warn only when documented disk or reclaimable-space thresholds are reached. Cleanup failures now stop with a non-zero error naming the affected path instead of silently reporting zero bytes removed.

The new `disk` command is reserved as a session name. Existing sessions named `profiles` remain compatible: `cdx clean profiles` still clears that session's transcripts, and profile-wide cleanup is selected only when `--tmp` or `--old-logs` is supplied.

### Banked Codex resets

For eligible Codex accounts, `cdx status` now displays the number of banked rate-limit resets returned by the Codex app-server. Detailed status JSON includes available reset identifiers, labels, grant timestamps, and expiration timestamps when the backend provides them.

`cdx reset <name>` consumes one available reset through Codex's idempotent reset-credit endpoint. The command is Codex-only, requires interactive confirmation unless `--yes` is supplied, handles backend eligibility outcomes explicitly, and refreshes status after activation. Status checks never consume resets automatically.

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
