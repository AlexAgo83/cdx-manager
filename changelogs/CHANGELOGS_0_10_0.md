# CDX Manager 0.10.0

## Highlights

- Inspect `CDX_HOME` and per-profile disk usage with readable, progress-aware reports.
- Find evidence-backed cleanup candidates and reclaim space through confirmed actions.
- Display and explicitly activate banked Codex rate-limit resets.

## Changes

### Disk usage and cleanup

`cdx disk` measures total `CDX_HOME` usage. `cdx disk profiles` adds an aligned per-profile table with size and share of total space, while `--candidates` adds reclaimable totals and evidence grouped by profile.

Interactive scans report their current stage and profile count on stderr so large profiles no longer appear stalled. JSON and redirected output remain unchanged.

Cleanup candidates are intentionally limited to temporary marketplace/plugin staging directories and old `.log` files. `cdx clean profiles --tmp` and `cdx clean profiles --old-logs DAYS` require confirmation before deletion; all other `cdx clean` log-truncation actions now require confirmation as well. Non-interactive automation must opt in with `--yes`.

A passive read-only check runs at most once per day and warns when documented total, reclaimable, category, or large-profile thresholds are reached. It never removes files automatically.

### Banked Codex resets

Eligible Codex accounts now show banked rate-limit reset counts in `cdx status`. Detailed JSON includes reset identifiers, labels, grant timestamps, and expiration timestamps when Codex provides them.

`cdx reset <name>` consumes one reset through Codex's idempotent reset-credit endpoint, requires confirmation unless `--yes` is supplied, and refreshes status after activation. Status checks never consume resets automatically.

### Compatibility and safeguards

`disk` and `reset` are reserved for new session names. Existing sessions named `profiles` remain compatible with `cdx clean profiles`; profile-wide cleanup is selected only when `--tmp` or `--old-logs` is present.

Cleanup failures now stop with a non-zero error naming the affected path instead of silently reporting zero bytes removed.

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
