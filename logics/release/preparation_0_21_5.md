# Release 0.21.5 preparation

Prepared locally on 2026-10-22. The checked-in release notes are `changelogs/CHANGELOGS_0_21_5.md`; the GitHub release title is the tag, `v0.21.5`.

## Scope

- Claude auth type in `cdx status`, with the setup-token expiry warning in status and doctor (#16, #21).
- Reliability fixes (#18):
  - `cdx ready` notification;
  - macOS keychain cleanup in `cdx login`;
  - bounded session-store lock;
  - hook path quoting;
  - atomic Claude settings write;
  - Windows-safe process check.
- Token price review (#20).
- Cleanup and tray command tests (#17, #19).
- Version metadata and README badge aligned to 0.21.5.

## Local receipts

- `npm test`: 1113 passed. `npm run lint`: passed. `logics-manager lint`: OK.
- Status checked against real profiles on macOS: TYPE shows `full-login` for `/login` profiles and `setup-token` for the others; every current setup-token has more than 200 days left.
