# Changelog (`0.6.1 -> 0.6.2`)

Release date: 2026-05-29

## Provider Support

- Added Antigravity provider support through the `agy` CLI with isolated session homes, launch settings, and transcript capture.
- Added Ollama provider support through `ollama run`, including model-backed session configuration and transcript capture.
- Added explicit `cdx add ollama <name> --model MODEL` registration so Ollama sessions do not depend on ambiguous session-name model defaults.

## Launch Settings

- Added bulk launch setting updates for all sessions, provider-filtered sessions, and named session subsets.
- Added shortcut launch setting commands for power, permission, fast mode, and model changes.
- Updated help and README command documentation for provider launch settings.

## Claude Behavior

- Fixed Claude auth reuse and status refresh behavior.
- Disabled Claude commit attribution by default for managed Claude sessions.

## Runtime Reliability

- Set `OLLAMA_NOHISTORY=1` for Ollama launch, status, and auth-check operations to avoid local history-file permission failures.
- Preserved provider-specific launch arguments across the transcript wrapper and fallback paths.

## Release Metadata and Documentation

- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.6.2`.

## Validation and Regression Coverage

- Added coverage for Antigravity launch specs and auth checks.
- Added coverage for Ollama session creation, model persistence, launch specs, and no-history environment handling.
- Added coverage for bulk and shortcut launch setting commands.
- Added coverage for Claude auth/status behavior and commit-attribution defaults.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `npm pack --dry-run`
