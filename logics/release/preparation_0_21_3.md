# Release 0.21.3 preparation

Prepared locally on 2026-10-13. The checked-in release notes are `changelogs/CHANGELOGS_0_21_3.md`; the GitHub release title is the tag, `v0.21.3`.

## Scope

- Corrective release: Claude in Chrome reachable from CDX Claude profiles (real Chrome directory linked into the redirected profile home on macOS and Linux).
- Version metadata and README badge aligned to 0.21.3.

## Local receipts

- `npm test`: 1079 passed. `npm run lint`: passed.
- Checked on macOS with the repository build: under the `claw` profile environment, `claude --chrome` installed `com.anthropic.claude_code_browser_extension.json` into the real Chrome `NativeMessagingHosts` and its browser tools answered. Before the fix that manifest was never written and `/chrome` saw no extension.
- Linux and Windows not exercised end to end: Tower's WSL has only snap Chromium (not linked by this change) and Tower's Windows Chrome has no Claude extension.
