# Changelog (`0.7.0 -> 0.7.1`)

Release date: 2026-05-29

## Headless Automation

- Switched `cdx run --json` Codex execution to the provider-native `codex exec --json` path so headless runs no longer depend on an interactive terminal launch mode.
- Switched Claude headless execution to `claude --print --output-format json` while preserving isolated auth homes, model selection, permission mode, and effort mapping.
- Preserved Codex unattended `auto` permission behavior in headless mode with an explicit `approval_policy="never"` config override.
- Kept provider stdout and stderr captured in artifact files while cdx stdout remains reserved for the final JSON payload.

## JSON Contract

- Added top-level `launcher: "cdx"` to `cdx run --json` result payloads so subprocess callers can identify cdx-manager responses directly.
- Ensured `launcher: "cdx"` is also present when provider auto-selection cannot find a suitable session.
- Added conservative token usage extraction for supported Codex and Claude JSON or JSONL stdout artifact shapes.
- Preserved all-null token usage when artifacts are missing, malformed, unsupported, or do not expose trusted usage data.

## Status Display

- Clamped Claude rate-limit percentage calculations to the `0..100` range so over-limit provider utilization cannot display negative remaining availability.
- Clamped cached status percentages defensively so already-persisted invalid values render as valid availability values.
- Colored fully depleted or invalid low availability as red and high availability above 80% as bright cyan.

## Planning Docs

- Added and completed Logics request, backlog items, and tasks for Orchestia headless token usage and provider-native launch modes.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.1`.

## Validation and Regression Evidence

- `python -m unittest discover -s test -p 'test_*_py.py'`
- `npm run lint`
- `npm test`
- `npm pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
- `python3 -m logics_manager lint --require-status`
