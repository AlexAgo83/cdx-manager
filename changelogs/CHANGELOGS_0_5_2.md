# Changelog (`0.5.1 -> 0.5.2`)

Release date: 2026-05-22

## Major Highlights

- Added transcript-based handoff between two sessions of the same provider.
- Added automatic launch prompting so the target Codex session reads `shared-context.md` and resumes without a manual instruction.
- Prepared the package metadata for the 0.5.2 release across npm, PyPI, CLI version output, and README install examples.

## Transcript-Based Session Handoff

- Added `cdx handoff <source> <target> [--json]`.
- Builds a shared context from the source session's latest captured launch transcript.
- Installs the generated context into the target session as `shared-context.md`.
- Preserves target account authentication and does not copy source credentials.
- Rejects same-session and cross-provider handoffs with explicit errors.
- Truncates very large transcripts to the most recent tail before writing the handoff context.

## Launch and JSON Output

- Passes an initial Codex prompt during handoff launch so the target session is told to read `$CODEX_HOME/shared-context.md`.
- Adds `launch_prompt` to `cdx handoff ... --json` output for non-interactive integrations.
- Keeps `--json` handoff mode non-launching while exposing source transcript, generated context, and installed target context paths.

## Documentation

- Updated CLI help and session-list command hints for `cdx handoff <source> <target>`.
- Updated the README feature summary and command table for transcript-based handoff.
- Updated the README badge and pinned installer example to `v0.5.2`.

## Validation and Regression Coverage

- Added CLI coverage for source-to-target handoff context generation.
- Added CLI coverage proving non-JSON handoff launches the target Codex session with the resume prompt.
- Kept full Python test coverage and Logics lint green.

## Validation and Regression Evidence

- `python -m pytest test -q`
- `python logics/skills/logics.py lint --require-status`
- `git diff --check`
