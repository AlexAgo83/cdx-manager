# CHANGELOGS_0_2_0

Release date: 2026-04-16

## CDX Manager 0.2.0

CDX Manager 0.2.0 focuses on operational reliability. It adds health checks, safe repair workflows, reset notifications, stronger session-store behavior, and clearer status output for choosing the best account.

### At a glance

- Added `cdx doctor` to inspect local CLI dependencies, `CDX_HOME` writability, missing session state, orphan profiles, and pending quarantines.
- Added `cdx repair` with dry-run-by-default behavior and `--force` for safe repairs.
- Added `cdx notify` to wait for reset events or the next recommended usable session.
- Added compact status output with `cdx status --small` / `cdx status -s`.
- Improved `cdx status` ranking so rows are sorted by practical availability.
- Added priority guidance that explains which session to use first and which one comes next.
- Added countdown reset formatting for reset times under 24 hours.
- Decorated CLI output with terminal-native color support while respecting `NO_COLOR`, `CLICOLOR`, and TTY behavior.
- Split the CLI implementation into smaller modules for status rendering, provider runtime, commands, and storage.

### Doctor and repair

- `cdx doctor [--json]` reports installation and data-layout health.
- `cdx repair [--dry-run] [--force] [--json]` plans repairs by default.
- Missing per-session state files can be recreated safely.
- Pending quarantine profile directories can be cleaned up.
- Orphan profiles are moved to quarantine with `--force` instead of being deleted directly.

### Notifications

- `cdx notify <name> --at-reset` waits for the selected session reset time.
- `cdx notify --next-ready` waits for the recommended session to become usable or due for refresh.
- `--poll seconds`, `--once`, and `--json` are supported.
- macOS desktop notifications are sent through `osascript` when available, with terminal output as the consistent fallback.

### Status improvements

- `cdx status` now includes a direct priority line before the usage tip.
- The priority line prefers immediately usable accounts, accounts with earlier relevant resets, and accounts without credit fallback when appropriate.
- Reset columns use countdowns such as `in 2h 30m` under 24 hours.
- The main `cdx` session list now formats updated timestamps as relative ages.
- JSON status output keeps a stable shape even when live Claude refresh fails; refresh warnings are written to stderr.

### Reliability and safety

- Session names now reject reserved command names including `doctor`, `repair`, and `notify`.
- Session removal uses a quarantine flow and surfaces cleanup failures instead of silently ignoring them.
- Session-store writes fsync the containing directory after atomic replacement.
- Session-store locking now fails explicitly when file locks cannot be acquired.
- Codex transcript launch now supports quoted `CDX_SCRIPT_ARGS` with a `{transcript}` placeholder.
- Codex launch falls back without transcript capture when the `script` wrapper is unavailable or fails before producing a transcript.
- Signal interruptions no longer trigger transcript fallback relaunches.

### Validation

```bash
npm run lint
npm test
./bin/cdx doctor
./bin/cdx repair --dry-run
./bin/cdx notify --next-ready --once
./bin/cdx --version
```

### Notes

- The package remains marked `private` in `package.json`; npm publication still requires an explicit policy change.
- No Git remote is configured in the current local repository, so this release is prepared locally and tagged locally only.
