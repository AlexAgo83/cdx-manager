# Changelog (`0.5.3 -> 0.5.4`)

Release date: 2026-05-23

## Major Highlights

- Added a Logics ADR for the code quality, security, performance, and test coverage improvements completed after `0.5.3`.
- Hardened bundle import path handling and launch prompt validation without changing CLI contracts or on-disk formats.
- Improved status parsing and provider handling internals for safer future maintenance.
- Added structured Codex app-server probe diagnostics while keeping the existing status API behavior compatible.

## Security and Runtime Hardening

- Hardened bundle relative path validation against traversal, absolute paths, and Windows drive paths.
- Validated provider launch `initial_prompt` type and length before it is passed into subprocess arguments.
- Replaced mutable signal-capture state with explicit `nonlocal` signal forwarding.
- Added Linux `notify-send` support with backend timeout handling and shell-free notification arguments.

## Status and Provider Internals

- Moved status extraction regex compilation to module-level constants.
- Added shared provider constants for Codex and Claude identity checks.
- Improved Claude status refresh handling for sync and async refresh functions without per-thread event loops.
- Added `fetch_codex_rate_limit_diagnostic()` to expose structured failure reasons such as missing auth home, initialize failure, app-server read failure, missing rate limits, and missing Codex CLI.

## CLI Parser Maintenance

- Factorized more CLI flag parsing through a shared flat-flag parser.
- Added `--flag=value` support where appropriate, including `cdx notify --poll=<seconds>`.
- Preserved existing usage errors and JSON/non-JSON output contracts.

## Documentation

- Added `logics/architecture/adr_001_code_quality_and_security_improvements.md` documenting the security, test, quality, and performance decisions.
- Updated package metadata, CLI version output, README badge, and pinned installer example to `v0.5.4`.

## Validation and Regression Coverage

- Added direct session-store rollback tests for add, remove, rename, and replace failure paths.
- Added status-source tests for key-value, Codex block, Claude block, artifact selection, reset timestamp parsing, and safe relative paths.
- Added notification tests for macOS, Linux, backend fallback, timeout, and argument handling.
- Added CLI parser tests for update, status, repair, export/import subsets, corrupt bundles, and clean behavior with and without logs.
- Added Codex app-server diagnostic tests for success and failure cases.

## Validation and Regression Evidence

- `npm test`
- `npm run lint`
- `python logics/skills/logics.py lint --require-status`
