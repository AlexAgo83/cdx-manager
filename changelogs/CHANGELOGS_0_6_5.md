# Changelog (`0.6.4 -> 0.6.5`)

Release date: 2026-05-29

## Installer Integrity

- Fixed standalone installer checksum resolution so the Unix installer can validate published GitHub archive checksums correctly.
- Added regression coverage for the release checksum lookup path used by the standalone installer.

## Claude Authentication

- Preserved the captured Claude setup-token transcript when token extraction fails, making failed login setup recoverable and easier to inspect.
- Reordered Claude status handling so authentication is checked before refreshing usage, avoiding noisy usage refresh failures when Claude credentials are absent or invalid.

## Codex Authentication

- Hardened Codex auth detection so an empty or unusable `auth.json` is no longer treated as an authenticated session.
- Added coverage for usable-token validation instead of relying on file presence alone.

## Auth Bundle Security

- Replaced the previous homegrown auth bundle encryption with AEAD encryption via `cryptography`.
- Added wrong-passphrase and auth bundle regression tests for the new encrypted bundle format.
- Updated CI and publish workflows to install Python package dependencies before running Python-backed lint, tests, and version validation.

## Release Metadata and Documentation

- Updated package metadata, CLI version output, README badge, pinned installer example, and release changelog to `v0.6.5`.

## Validation and Regression Evidence

- `npm run lint`
- `npm test`
- `python -m build --sdist --wheel`
- `npm pack --dry-run`
