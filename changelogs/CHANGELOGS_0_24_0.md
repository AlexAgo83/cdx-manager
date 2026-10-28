# CDX Manager 0.24.0

This release lets a dashboard, a terminal board or a chat agent ask cdx which sessions are working, waiting for their user, done or stopped by a usage limit, and lets detached background runs fail over to another account.

## Agent state

- `cdx set <name> --agent-state on` installs the provider hooks that record each session's state, without desktop alerts; sessions with `--notify on` record it too.
- Every hook event updates one small record per session under `$CDX_HOME/state/agents/`, written atomically, even when alerts are muted.
- `cdx agents [--max-age-hours N] [--json]` lists them, waiting first: `working`, `waiting`, `done`, `failed`, `limit` (with `reset_at` when known) or `ended` when the launching process is gone. Records older than N hours (24 by default) are dropped.
- A `limit` state needs the same two signals as run failover: the provider's own exhaustion error and a refreshed account status that confirms it.
- The prompt head (120 characters) is kept only with `--notify-preview on`.
- Codex has no failure hook, so a Codex session never reaches `failed` or `limit`. Codex plugins installed before this release keep their old hooks until reinstalled (`--notify off`, one launch, `--notify on`).

## Runs

- `cdx run --detach --failover` is now accepted: the detached child watches the run and applies the failover rule, and the run registry records each move under the same `run_id`.
