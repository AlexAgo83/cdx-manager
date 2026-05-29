# Changelog (`0.7.1 -> 0.7.2`)

Release date: 2026-05-29

## Update Reliability

- Fixed Unix standalone update detection for installs under `~/.local/share/cdx-manager/<version>` so `cdx update` uses the standalone installer instead of incorrectly upgrading npm.
- Added a post-update PATH verification check that runs the resolved `cdx -v` and warns when another older executable shadows the updated install.
- Reduced the environment passed to the post-update version check so sensitive variables are not forwarded to the verification subprocess.
- Aligned the PowerShell standalone installer with the Windows launcher by accepting `py`, `python`, or `python3`.

## Headless Usage and Stats

- Persisted normalized token usage from `cdx run --json` into launch history for future aggregation.
- Added `cdx stats [name] [--since 7d|today|DATE] [--from DATE] [--to DATE] [--json]` to aggregate launches, successes, failures, duration, known usage runs, and token totals by session.
- Continued extracting provider stdout usage even when a headless provider exits with an error, preserving useful usage data from structured failure payloads.

## RTK Preference

- Added `cdx set <session> --rtk on|off` and `cdx unset <session> --rtk` to store a per-session preference that encourages assistants to use RTK for noisy terminal commands.
- Injected the RTK preference into interactive and headless launch prompts without rewriting commands automatically.
- Added `cdx doctor` detection for the `rtk` CLI.

## Coverage and Tests

- Added focused coverage for update checking, context storage, RTK launch preferences, post-update shadow warnings, and per-session stats aggregation.
- Increased the Python test suite to 260 tests.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.2`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `npm pack --dry-run`
- `node bin/cdx.js -v`
- `python3 -m build`
- `python3 -m twine check dist/*`
