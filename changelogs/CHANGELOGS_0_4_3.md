# Changelog (`0.4.2 -> 0.4.3`)

Release date: 2026-04-19

## Major Highlights

- Generated from 1 code commit between `v0.4.2` and `HEAD` on 2026-04-19.
- Touched areas: Windows Codex status discovery, status formatting, and regression coverage.
- `cdx status` now reads Codex's structured Windows `rate_limits` payloads instead of falling back to `n/a`.
- Reset dates now render in the same short format as the rest of the UI, so the table stays readable.
- When a session profile has no usable Codex status artifact, `cdx` can fall back to the global Codex home on Windows.

## Generated Commit Summary

## Codex Status on Windows

- Added support for structured `rate_limits` data emitted by Codex's JSONL session history.
- Kept support for the older transcript-style status blocks, so existing artifacts still resolve.
- Narrowed the global-home fallback to real `cdx` runs on the default home, which avoids cross-contaminating temporary test homes.

## Status Formatting

- Normalized structured reset timestamps to the short `Apr 25 18:52` style used elsewhere in `cdx status`.
- Preserved the existing relative labels such as `in 3h 57m` in the rendered table.

## Validation and Regression Coverage

- Added a regression test for structured Codex rollout rate limits.
- Kept the existing session-service and CLI validation suite green.

## Validation and Regression Evidence

- `python -m unittest discover -s test -p "test_session_service_py.py"`
- `python -m unittest discover -s test -p "test_cli_py.py"`
- `python -m unittest discover -s test -p "test_runtime_py.py"`
- `node bin/cdx.js status`
