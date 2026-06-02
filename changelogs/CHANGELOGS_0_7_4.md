# Changelog (`0.7.3 -> 0.7.4`)

Release date: 2026-06-02

## Security and Privacy

- Rejected `.` and `..` as session names so profile and state paths cannot escape their managed directories.
- Added import-bundle regression coverage for unsafe dot-path session names.
- Redacted headless `cdx run` prompt arguments before persisting launch history while keeping provider execution unchanged.
- Made headless `cdx run` perform a live provider auth probe instead of trusting only local credential files.
- Hardened Claude auth invalidation so invalid Claude credentials are recorded as logged out during refresh and status handling.

## Installer Integrity

- Changed standalone Unix and PowerShell installers to fail closed when no official checksum is available.
- Added the explicit `CDX_ALLOW_UNVERIFIED=1` override for users who intentionally accept an unverified archive.
- Updated README security guidance for standalone installer checksum behavior.

## Headless and Selection Behavior

- Added the next-assistant recommendation command and improved resolved run reasoning-effort reporting.
- Preserved stable provider-specific launch metadata while adding stricter headless auth validation.

## Maintainability

- Extracted headless run prompt, error-code, and JSON payload helpers into `src/run_command.py`.
- Reduced the size of `src/cli_commands.py` without changing the public `cdx run --json` contract.

## Coverage and Tests

- Added regression coverage for dot-path session names, unsafe imported sessions, redacted headless history prompts, forced live auth probes, and unauthenticated headless runs.
- Increased the Python test suite to 276 tests.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.4`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `npm audit --omit=dev --json`
- `sh -n install.sh`
- PowerShell parser check for `install.ps1`
- `python3 -m logics_manager lint --require-status`
