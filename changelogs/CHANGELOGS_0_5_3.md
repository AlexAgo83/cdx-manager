# Changelog (`0.5.2 -> 0.5.3`)

Release date: 2026-05-23

## Major Highlights

- Added Claude-compatible handoff launch prompting so Claude targets are told exactly which `shared-context.md` file to read.
- Added Claude launch transcript capture, enabling transcript-based handoff from Claude source sessions.
- Enabled cross-provider transcript handoff between Codex and Claude sessions.
- Prepared the package metadata for the 0.5.3 release across npm, PyPI, CLI version output, and README install examples.

## Claude Handoff

- Passes the handoff prompt to Claude as the initial prompt argument during launch.
- Installs shared context into the target Claude session profile and references the concrete `shared-context.md` path in the prompt.
- Captures Claude launch transcripts under the session's `claude-home/log/` directory using the same transcript wrapper path as Codex.
- Preserves Claude `HOME` isolation while running through the transcript wrapper.

## Cross-Provider Handoff

- Allows `cdx handoff <source> <target>` when the source and target providers differ.
- Keeps generated handoff context provider-neutral while still recording source and target provider metadata.
- Preserves target account authentication and does not copy source credentials.

## Documentation

- Updated the command table to document Codex and Claude handoff targets, including cross-provider handoff.
- Updated the README badge and pinned installer example to `v0.5.3`.

## Validation and Regression Coverage

- Added CLI coverage for Claude-to-Claude transcript handoff.
- Added CLI coverage for Codex-to-Claude handoff.
- Added CLI coverage proving non-JSON Claude handoff launches Claude with the resume prompt.
- Updated existing Claude launch coverage to verify transcript-wrapped launches.

## Validation and Regression Evidence

- `python3 -m pytest test/test_cli_py.py test/test_runtime_py.py`
- `python3 -m pytest`
- `npm run lint`
- `npm test`
