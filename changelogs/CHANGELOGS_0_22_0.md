# CDX Manager 0.22.0

This release adds account-aware session recovery, clearer run controls, and more useful usage reporting. It also hardens credential handling and fixes several run and status edge cases.

## Account choice and recovery

- Set an account's automatic selection policy with `cdx set <name> --policy use|ask-first|never`. The policy is respected when CDX chooses an account for a run or rescue.
- `cdx rescue` can hand a limit-stopped conversation to a ready account. It also detects limit stops in the transcript and avoids duplicate rescue attempts.
- `cdx status` reports when an account may run out at its current pace and includes ISO 8601 reset times in JSON output.
- Claude conversations keep their own names, and handoffs work when a session has used multiple workspaces.

## Run and usage tools

- `cdx run` accepts a label and a concurrency cap. Cap checks, hook ownership, and blocked-status reporting have been corrected.
- Interactive session launch accepts `--task` and an optional `--end-state` to describe the authorized goal.
- `cdx stats --by project|model` breaks down usage, and stats can show estimated time saved by RTK over the selected period.
- Read-only session retrospectives are available on demand for an account.
- Profiles can share Claude auto-memory, and RTK history can be shared across profiles.
- One-hour cache writes are priced at the correct 2× rate.

## Security and reliability

- Credential isolation, backup-bundle import, session-name handling, and setup-token logging are hardened.
- Runtime fixes cover reset-time parsing, run hooks and status, and small CLI and documentation inconsistencies.
- The security policy is documented in `SECURITY.md`.
