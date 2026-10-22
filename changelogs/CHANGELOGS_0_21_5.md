# CDX Manager 0.21.5

## Claude logins

- `cdx status` shows each Claude profile's auth type in a TYPE column: `setup-token` or `full-login` (a `/login` run inside the profile). It also appears in the single-session view and as `auth_type` in `--json`. Within 30 days of a setup-token's one-year expiry, the column shows `setup-token 12d`, or `setup-token expired` once it has lapsed, and `cdx doctor` warns with the `cdx login` command to run. Based on work by Nicolas Rigaudy (#15, #16, #21).
- The operations guide explains why a setup-token never loads claude.ai connectors such as Microsoft 365, and how to switch with `/login`.
- On macOS, `cdx login` on a Claude profile now also removes the profile's keychain `/login`, so the new setup-token is the one used at launch. Before, the keychain login kept winning. The misleading "falling back to claude setup-token" message is reworded (#18).

## Fixes

- `cdx ready` never showed its notification: the scheduled job ran `cdx notify`, which now only serves agent hooks. On macOS the job was also written under the profile home inside a cdx session, where launchd never reads it (#18, #21).
- Windows:
  - the session store lock now waits up to 120 seconds instead of failing after 10;
  - the process-alive check no longer sends Ctrl+C to the process it probes (#18).
- Agent alert hooks work when the cdx path contains a space. Claude's `settings.json` is written atomically, through symlinks, and keeps its permissions (#18).
- Token prices reviewed on 2026-10-22:
  - `claude-sonnet-5-5` cache reads are $0.10/MTok;
  - `claude-haiku-5-5` is added;
  - context variants such as `claude-opus-5-5[1m]` are priced at the base model's rates (#20).

## Housekeeping

- `runs.json` keeps every running run plus the newest 500 finished ones.
- Handoff entries older than 7 days are deleted when a new one is prepared.
- Dead log-rotation code and duplicated helpers are removed.
- New tests cover the state-changing `cdx tray` commands (#17, #19).
