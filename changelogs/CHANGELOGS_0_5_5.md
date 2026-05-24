# Changelog (`0.5.4 -> 0.5.5`)

Release date: 2026-05-24

## Major Highlights

- Fixed Claude usage probing for OAuth credentials by using bearer-token authentication.
- Improved `cdx status` guidance with progress output, conservative reset timing, near-empty account handling, and last-launched session context.
- Made encrypted auth exports lightweight by backing up provider credential files instead of full profile caches, logs, and runtime artifacts.

## Usage and Status

- Added progress output while `cdx status` resolves session statuses in text mode, while keeping `--json` output clean.
- Added a `Current:` line under the priority recommendation showing the last launched session, useful before running a handoff.
- Removed the older status tip line now that status output carries actionable priority and current-session context.
- Treated sessions with `5%` or less availability as empty for priority recommendations, while preserving the true percentage in the table.
- Added a conservative one-minute reset countdown margin so users are less likely to switch back before a reset is usable.

## Claude Usage Handling

- Fixed the Claude rate-limit probe to send OAuth access tokens as `Authorization: Bearer ...`.
- Surfaced Claude HTTP failures without rate-limit headers as structured refresh warnings, including API error text when available.
- Preserved existing fallback behavior for unavailable network probes and historical status data.

## Export and Backup

- Limited `cdx export --include-auth` to provider credential files:
  - Codex: `auth.json`
  - Claude: `claude-home/.claude/.credentials.json`, `claude-home/.claude.json`, and legacy `claude-home/auth.json`
- Excluded profile caches, logs, SQLite usage databases, temporary files, and provider runtime artifacts from auth bundles.
- Added export progress output in text mode and a final summary with bundle size, auth file count, and auth data size.
- Kept `cdx export --json` clean and added bundle metrics to its JSON payload.

## Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.5.5`.
- Clarified that encrypted auth exports include credential files rather than full profile caches or logs.

## Validation and Regression Coverage

- Added regression coverage for Claude HTTP failures without usage headers.
- Added status rendering tests for progress output, last-launched context, near-empty priority handling, and removed tip text.
- Added export/import tests proving auth bundles exclude non-auth profile files such as `logs_2.sqlite`.

## Validation and Regression Evidence

- `python3 -m pytest test/test_cli_py.py test/test_session_service_py.py`
- `python3 -m pytest test/test_runtime_py.py test/test_cli_py.py test/test_status_source_py.py`
