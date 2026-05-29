# Changelog (`0.6.5 -> 0.7.0`)

Release date: 2026-05-29

## Headless Automation

- Added `cdx run --json` as a headless execution contract for automation clients such as Orchestia.
- Added explicit session execution, provider-based auto-selection, inline prompt and prompt-file support, working-directory validation, timeout handling, and stable run metadata.
- Kept JSON mode stdout reserved for the final response so callers can parse command output without terminal UI noise.
- Returned structured cdx-side and provider-side error envelopes for missing provider CLIs, invalid launch inputs, provider start failures, disabled sessions, and reasoning validation errors.

## Session Selection

- Added `cdx select --json` with deterministic ranking from provider match, readiness, cooldown, quota health, configured priority, reasoning capability, and session name.
- Reused the same selector from `cdx run --provider ...`.
- Added priority handling improvements, including configured-priority tie-breaking and clearing selection priority.
- Allowed ready selection for local providers where remote quota signals are not applicable.

## Reasoning Effort

- Added provider-neutral `--reasoning-effort low|medium|high` handling.
- Kept `--power` as a compatibility alias and rejected conflicting values with cdx-sourced JSON errors.
- Mapped normalized effort into Codex launch options while leaving clear extension points for other providers.

## Artifacts and Diagnostics

- Added transcript, stdout, and stderr artifact reporting for headless runs.
- Returned absolute artifact paths and normalized nullable token usage fields on success and failure responses.
- Hardened artifact and timeout tests to cover provider failures and unknown usage.

## Documentation and Release Readiness

- Documented the Orchestia headless delivery, headless CLI options, selection reasons, and JSON error stream behavior.
- Completed Logics release-gate documentation with rollback coverage, project changelog, release notes, duplicate triage, and release gate artifacts.
- Carried forward the `v0.6.5` release checksum metadata so standalone installer integrity checks can resolve the previous release.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.0`.

## Validation and Regression Evidence

- `python -m py_compile bin/cdx src/*.py test/test_*_py.py`
- `python -m unittest discover -s test -p 'test_*_py.py'`
- `npm run lint`
- `npm test`
- `npm pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
