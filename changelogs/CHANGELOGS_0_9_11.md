# CDX Manager 0.9.11

## Highlights

- Hardened transcript cleanup so captured handoff logs strip ANSI and control-sequence noise before reuse.
- Broadened lint coverage with Ruff's bugbear rules and fixed the newly surfaced issues.
- Split the CLI facade into dedicated argument and helper modules, reducing the size of the main command surface without changing user-facing commands.

## Changes

### Transcript and status reliability

Script-captured transcripts now remove additional terminal control noise before they are parsed or copied into handoff context.

Status and session helper internals also gained focused validation coverage for merge behavior, malformed records, and rate-limit parsing.

### CLI maintainability

The CLI command layer now reuses shared JSON, table, and parser helpers from extracted modules. The public CLI entrypoint remains stable, while tests can exercise smaller units directly.

Shared OAuth token cleanup and JWT decoding helpers were deduplicated into the Claude usage path so provider status code uses the same parsing behavior in one place.

### Validation coverage

Ruff now checks a wider rule set, including bugbear rules, while keeping only deferred stylistic exceptions out of the release gate.

New regression tests cover:

- Codex rate-limit payload parsing
- provider launch argument construction
- session status merge and validation helpers
- handoff transcript control-sequence cleanup

## Validation

- `npm run release:validate`
- `npm run lint`
- `npm test`
- `logics-manager lint --require-status`
- `logics-manager audit`
- `git diff --check`
- `npm --cache /private/tmp/cdx-npm-cache pack --dry-run`
- `python -m build`
- `python -m twine check dist/*`
