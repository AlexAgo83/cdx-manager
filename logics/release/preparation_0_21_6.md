# Release 0.21.6 preparation

Prepared locally on 2026-10-22. The checked-in release notes are `changelogs/CHANGELOGS_0_21_6.md`; the GitHub release title is the tag, `v0.21.6`.

## Scope

- Full audit follow-ups:
  - Windows and security (#23);
  - reliability (#24);
  - CLI consistency, schema codes, bundle KDF and locked cargo (#25).
- Windows update check (#22) and `--scrub-env` (#26).
- PyPI Trusted Publishing (#27). This is the first release published without `PYPI_API_TOKEN`.
- Version metadata and README badge aligned to 0.21.6.

## Local receipts

- `npm test`: 1123 passed. `npm run lint`: passed. `cargo test --locked`: 105 passed. `logics-manager lint`: OK.
- The Windows items were reproduced and verified on a Windows 11 host with a French locale and WSL Ubuntu:
  - launcher exit code;
  - WSL argument passing;
  - task scheduling with an ISO date;
  - typographic-quote escaping.
