# Changelog (`0.5.0 -> 0.5.1`)

Release date: 2026-05-22

## Major Highlights

- Replaced Codex status scraping with a structured local Codex app-server rate-limit probe.
- Kept transcript and JSONL status parsing as a legacy fallback when the local Codex app-server is unavailable.
- Prepared the package metadata for the 0.5.1 release across npm, PyPI, CLI version output, and README install examples.

## Codex Status Resolution

- Added a Codex app-server JSON-RPC client that calls `account/rateLimits/read` for each isolated Codex session profile.
- Normalized app-server rate-limit snapshots into the existing `cdx status` output fields: 5-hour remaining percentage, weekly remaining percentage, reset times, credits, and source metadata.
- Preserved multi-account isolation by running each probe with the session-specific `CODEX_HOME`.
- Updated status and launch tips so `/status` transcript capture is no longer presented as the normal Codex refresh path.

## Packaging

- Bumped `package.json`, `package-lock.json`, `pyproject.toml`, and `src/cli.py` to `0.5.1`.
- Updated the README version badge and pinned installer example for `v0.5.1`.

## Validation and Regression Coverage

- Added runtime coverage for Codex app-server JSON-RPC probing and rate-limit normalization.
- Added session-service coverage proving app-server status is preferred over legacy transcript artifacts.
- Updated CLI coverage for the revised Codex status guidance.

## Validation and Regression Evidence

- `python3 -m unittest discover -s test -p 'test_*_py.py'`
- `python logics/skills/logics.py lint --require-status`
- `python3 bin/cdx status --json`
