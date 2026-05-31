# Changelog (`0.7.2 -> 0.7.3`)

Release date: 2026-05-31

## Status Display

- Rounded Codex credit balances in the `cdx status` `CR` column to two decimal places.
- Applied the same credit formatting to the single-session status detail view.
- Parallelized status resolution across sessions with a bounded worker pool while preserving cache behavior and final row ordering.
- Added visible per-session progress for text status checks, including `Checked <session> (x/y)` messages for refreshed sessions.

## Stats and History Output

- Improved `cdx stats` text output with colorized headings, sessions, token totals, durations, and metadata when color is enabled.
- Reformatted long duration values into readable day/hour/minute forms such as `2h 05m`.
- Marked active sessions with `*` in `cdx stats`, matching `cdx status`.
- Improved `cdx history` and `cdx history --summary` with colorized headings, success/failure states, durations, and metadata.
- Marked active sessions with `*` in `cdx history` text output without changing JSON payloads.

## Coverage and Tests

- Added regression coverage for status credit rounding, parallel status refresh, status progress messages, colorized stats/history output, readable duration formatting, and active-session markers.
- Increased the Python test suite to 262 tests.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.3`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `npm pack --dry-run`
- `node bin/cdx.js -v`
- `python3 -m unittest discover -s test`
- `python3 -m build`
- `python3 -m twine check dist/cdx_manager-0.7.3*`
