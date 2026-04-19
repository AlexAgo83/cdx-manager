# Changelog (`0.3.4 -> 0.4.0`)

Release date: 2026-04-16

## Major Highlights
- CDX Manager 0.4.0 adds portable session backup and restore, surfaces cached release-update notices inside the CLI, and tightens Codex status isolation across multiple accounts.

## Generated Commit Summary

## Portable session bundles

- Added `cdx export <file>` and `cdx import <file>` for moving sessions between machines.
- Added optional encrypted auth export with `--include-auth` and interactive or environment-driven passphrase handling.
- Added subset export/import support with `--sessions`.
- Preserved per-session state alongside session records so imported environments keep their local metadata.
- Added bundle schema validation and integrity checks during import.

## Update awareness and installer hardening

- Added cached GitHub release checks so the CLI can warn when a newer `cdx-manager` release is available without hitting the network on every command.
- Surfaced update notices in interactive output and structured JSON warnings.
- Hardened the standalone install scripts to consume official release-archive checksums when available.
- Documented the checksum-backed installer flow and backup/restore usage in the README.

## Status isolation fix

- Fixed Codex status parsing so boxed blank lines in TUI transcripts no longer drop the `Account:` context line.
- Restored account-aware status selection when multiple sessions contain similar `/status` blocks.
- Added regression coverage for mixed-account transcript selection and bundle export/import flows.

## Validation and Regression Evidence

```bash
npm run lint
npm test
python3 -m build --no-isolation
```
