# CDX Manager 0.9.15

## Highlights

- Hardened concurrent session, run, and file updates against lost or partial writes.
- Improved status accuracy when multiple Codex and Claude data sources disagree.
- Tightened credential handling, headless process cleanup, CLI parsing, and release gating.

## Changes

### Reliable state and status

Session and run read-modify-write operations now stay under a single lock, and context, settings, and bundle exports use atomic replacement. Merge imports preserve live local runtime state, malformed JSONL usage records no longer discard an entire run, and refresh tolerates late or failed per-session writes.

Status selection now ranks structured, attributed, and fresh records consistently, preserves compatible fields across equally trusted candidates, handles year-wrapped reset timestamps, and treats a zero credit balance as no remaining credit.

### Safer auth and process handling

Credential files and directories are private from creation, and temporary Claude setup-token transcripts are removed on both success and failure.

Headless timeouts terminate the complete process group, while signal exits consistently return `128 + signum`.

### CLI, updates, and release automation

Argument parsing now rejects conflicting target selectors and flags used as values, while subcommand help remains scoped to the subcommand. Headless selection no longer imposes an implicit reasoning-effort floor.

Failed Logics Manager version checks are no longer cached, missing updater return codes fail safely, non-epoch Claude reset headers no longer abort refresh, and publication now gates on the latest CI run for the release commit.

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
