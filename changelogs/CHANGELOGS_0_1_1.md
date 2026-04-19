# Changelog (`0.1.0 -> 0.1.1`)

Release date: 2026-04-16

## CDX Manager 0.1.1

CDX Manager 0.1.1 is the first packaged release of the multi-provider terminal session manager for Codex and Claude accounts.

It turns the initial Logics-scoped idea into a usable CLI: isolated per-session auth homes, interactive provider launch, status extraction from local artifacts, Claude usage refresh through Anthropic rate-limit headers, log capture, cleanup commands, and release-ready package metadata.

### At a glance

- Added the `cdx` CLI entrypoint with conventional `--help`, `--version`, session listing, creation, launch, copy, removal, login, logout, clean, and status commands
- Added persistent session storage under `CDX_HOME`, with URL-encoded session names and per-session rehydration state
- Added explicit Codex and Claude provider support with isolated `CODEX_HOME` / `HOME` environments
- Added auth bootstrap and guardrails before launch, including provider-specific status checks and interactive login/logout commands
- Added terminal signal forwarding so launched provider CLIs receive interrupts and exits cleanly
- Added global and per-session status views with 5-hour, weekly, available, reset, and updated fields
- Added fallback status parsing from provider JSONL history and terminal transcript logs
- Added Claude automatic usage refresh from Anthropic API rate-limit headers
- Added terminal transcript capture through `script`, rotated launch logs, and the `cdx clean` command
- Migrated the implementation to Python while keeping npm-based install and validation scripts
- Added root packaging metadata, MIT license, README, contribution guidance, and release notes

### Session management

- `cdx add <name>` creates Codex sessions by default.
- `cdx add claude <name>` creates Claude sessions with a dedicated `claude-home`.
- `cdx <name>` launches the selected provider in an isolated environment.
- `cdx cp <source> <dest>` copies a session while preserving provider isolation.
- `cdx rmv <name> [--force]` removes the session registry entry and its auth directory.
- Session state is stored in a versioned JSON registry and per-session state files under `CDX_HOME`.

### Authentication and launch flow

- Codex sessions use `codex login status`, `codex login`, and `codex logout`.
- Claude sessions use `claude auth status`, `claude auth login`, and `claude auth logout`.
- Launches are blocked when a session is not authenticated, with clear recovery instructions.
- Signals from the wrapper process are forwarded to the child provider process.
- Codex launches show a reminder to run `/status` inside Codex when usage data needs refreshing.

### Usage and status reporting

- `cdx status` renders an aligned table for all sessions.
- `cdx status <name>` renders a detailed view for one session.
- `--json` is supported for both global and detail status views.
- Status rows include `AVAILABLE`, `5H LEFT`, `WEEK LEFT`, `RESET 5H`, `RESET WEEK`, and `UPDATED`.
- Available percentage is computed from the stricter remaining quota window.
- Cached statuses are enriched from newer or more detailed local artifacts when available.

### Codex status extraction

- Parses Codex `/status` blocks from logs and JSONL history.
- Handles ANSI / terminal control sequences and narrow terminal layouts.
- Extracts 5-hour and weekly reset values independently.
- Uses account identity in Codex status blocks to avoid accepting pasted status output from another account.
- Prefers direct launch logs over noisier conversational rollout JSONL artifacts.

### Claude status extraction

- Parses `Current session` and `Current week` blocks from Claude transcripts.
- Extracts 5-hour reset values from `Current session`, including AM/PM formats such as `Resets at 5:00 AM`.
- Extracts weekly reset values from `Current week`.
- Keeps Claude 5-hour and weekly reset values separate in status output.
- Refreshes Claude usage automatically from Anthropic rate-limit headers when credentials are available.

### Local time behavior

- Claude API reset timestamps are formatted in the machine's local timezone.
- Log-derived time-only reset values are inferred in the local timezone.
- Status `updated_at` values from API, JSONL, and file metadata are normalized to local ISO timestamps.

### Logging and cleanup

- Provider launches are captured to local transcript logs via `script`.
- Launch logs include unique timestamped filenames to avoid overwriting active or recent transcripts.
- Logs are rotated around the 10 MB threshold.
- `cdx clean [name]` clears launch transcript logs for one session or all sessions.

### Packaging

- Published package version is `0.1.1`.
- The npm tarball is restricted to the CLI entrypoint, source package, README, license, and release changelogs.
- Local project-only files such as `.claude`, Logics workflow docs, and tests are excluded from the package tarball.

### Validation

```bash
npm run lint
npm test
python3 bin/cdx --version
npm --cache /tmp/cdx-npm-cache pack --dry-run
```

### Notes

- This is the first release changelog, so it summarizes the full history from the initial Logics bootstrap through the 0.1.1 release preparation.
- The package remains marked `private` in `package.json`; publication requires intentionally changing that release policy.
