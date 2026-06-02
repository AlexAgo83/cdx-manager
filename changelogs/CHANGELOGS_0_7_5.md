# Changelog (`0.7.4 -> 0.7.5`)

Release date: 2026-06-02

## Launch Settings

- Applied persisted `--model` settings to interactive Codex and Claude launches, matching the existing headless behavior.
- Switched Codex model launches to the explicit `--model` flag for both interactive and headless runs.
- Documented provider-specific model mapping for Codex, Claude, and Ollama.

## Fast Mode

- Fixed `--fast on` so it clears the default stored power setting and actually launches Codex and Claude with low effort.
- Made explicit `--power` settings disable fast mode again, keeping launch settings readable and predictable.
- Restored `power=medium` when `--fast off` is set and no explicit power is present.

## Coverage and Tests

- Added regression coverage for persisted model settings on interactive Codex and Claude launches.
- Added regression coverage for `fast on` launching Codex with `model_reasoning_effort="low"` and Claude with `--effort low`.
- Increased the Python test suite to 280 tests.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.5`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `python3 -m pytest -q`
- `npm audit --omit=dev --json`
- `sh -n install.sh`
- PowerShell parser check for `install.ps1`
- `python3 -m logics_manager lint --require-status`
