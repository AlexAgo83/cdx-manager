# Changelog (`0.7.5 -> 0.7.6`)

Release date: 2026-06-05

## Claude Launches

- Normalized Claude model names before invoking Claude Code so persisted API-style IDs such as `claude-sonnet-4-5-20250929` launch as the Claude Code CLI form `claude-sonnet-4-5`.
- Added compatibility for marketing-style Claude model values such as `sonnet-4.5` while preserving unknown custom model values unchanged.
- Applied the same Claude model normalization to both interactive launches and headless `cdx run` launches.

## Release Integrity

- Added official standalone release archive checksums for `v0.7.5` so verified installer upgrades can resolve the previous release.
- Added regression coverage for the `v0.7.5` release checksum metadata.

## CI Hardening

- Restricted GitHub Actions workflow token permissions for the CI workflow.

## Coverage and Tests

- Added regression coverage for Claude CLI model normalization in runtime launch specs and interactive CLI launch behavior.
- Increased the Python test suite to 285 tests.

## Release Metadata

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.7.6`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `node bin/cdx.js --version`
- `npm audit --omit=dev --json`
- `sh -n install.sh`
- PowerShell parser check for `install.ps1`
- `python3 -m logics_manager lint --require-status`
