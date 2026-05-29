# Changelog (`0.6.3 -> 0.6.4`)

Release date: 2026-05-29

## Claude Multi-Account Authentication

- Fixed Claude auth status reconciliation so `cdx status` no longer reports stale `authenticated` state after Claude CLI credentials are missing or logged out.
- Stopped trusting `credentials/default.json` alone as proof of Claude login; cdx now validates real Claude CLI credentials or probes `claude auth status`.
- Preferred Claude CLI credentials over setup-token fallback files for usage refreshes, avoiding HTTP 400 failures from stale or malformed fallback tokens.
- Hardened setup-token extraction to ignore placeholder hints such as `CLAUDE_CODE_OAUTH_TOKEN=<token>` and continue scanning for the real `sk-ant-oat...` token.
- Stripped terminal ANSI sequences from captured setup tokens before saving them.

## Status Accuracy

- Added an explicit `AUTH` column to `cdx status` and `auth_status` fields to JSON rows.
- Marked Ollama and Antigravity authentication as `n/a` in the status table because cdx does not manage provider login for those sessions.
- Excluded explicitly logged-out sessions from priority recommendations while still showing their cached quota rows.
- Parsed Claude "No stats available yet" screens as a usable zero-usage status instead of leaving the row with unknown quota.

## Release Metadata and Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.6.4`.

## Validation and Regression Coverage

- Added regression coverage for Claude setup-token placeholder extraction, malformed fallback tokens, CLI credential precedence, status auth rendering, and logged-out priority filtering.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
