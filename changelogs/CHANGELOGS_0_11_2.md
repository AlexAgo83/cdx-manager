# CDX Manager 0.11.2

## Highlights

- Improved Codex Business auth diagnostics without changing login or launch behavior.
- Added stale-auth log warnings to help repair the affected profile only.
- Documented the Business `account_id` ambiguity and the `cdx login <name>` repair path.

## Changes

### Codex Business auth diagnostics

`cdx doctor` now reports shared Codex `tokens.account_id` values as workspace-level evidence on Business plans, not proof that two profiles are using the same user account. When recent `/status` transcript output exposes different observed users for profiles that share the same account id, doctor marks that as expected instead of a duplicate-user warning.

Codex auth diagnostics now include a masked `account_id` and an observed account from recent logs when available. Raw tokens remain excluded from JSON output.

### Stale auth hints

`cdx doctor` scans recent Codex profile logs for common expired-auth markers such as `401`, `token_expired`, and `authentication token is expired`. When found, it emits `codex_stale_auth_logs` with a direct `cdx login <name>` recommendation for the affected isolated profile.

## Validation

- `npm run lint`
- `npm test`
- `logics-manager health`
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
