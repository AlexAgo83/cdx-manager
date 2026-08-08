## item_063_add_budget_and_fallback_model_as_pinnable_launch_settings - Add budget and fallback-model as pinnable launch settings
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Quota-aware execution
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Claude Code 2.1.226 ships `--max-budget-usd` and `--fallback-model`; cdx maps neither, so a user who wants either must launch the provider outside cdx and lose account isolation.
- A spend ceiling is the natural companion to quota routing and cdx cannot express it: `cdx stats` measures spend after the fact and nothing can cap it.
- `--fallback-model` is the provider's own in-process answer to unavailability, which makes it both immediately useful and a useful reference point for the cross-account failover this request builds later.

# Scope
- In:
  - Add `budget` and `fallback_model` to `_normalize_launch_settings` in `src/session_service.py`, with `budget` rejecting non-numeric, non-positive, NaN and infinite values, and `fallback_model` reusing the existing model character and length rules.
  - Add both keys to the allowed set in `unset_launch_settings`.
  - Add the `--budget` and `--fallback-model` options to the `cdx set` and `cdx unset` tables in `src/cli_args.py`, following the `--model` and `--priority` entries.
  - Add both to the display list in `src/cli_helpers.py` and to `_format_launch_configs` in `src/commands/status.py`.
  - Map both to Claude launch arguments in `src/provider_runtime.py` alongside the existing `--effort` and `--model` mapping.
  - Report in `cdx configs` that both settings are inert for Codex sessions rather than rejecting them at launch.
- Out:
  - Any shortcut command of the form `cdx budget <name> <value>`, which can follow once the settings exist.
  - Enforcing the budget inside cdx; the ceiling is the provider's to apply.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: `cdx set <name> --budget 5` then `cdx config <name> --json` reports the stored ceiling, and `cdx unset <name> --budget` removes it.
- AC2: `--budget 0`, `--budget -1`, `--budget abc` and a value above the accepted maximum are each rejected with an error naming the setting, and nothing is written to the store.
- AC3: `cdx set <name> --fallback-model <model>` is validated identically to `--model`, including the rejection of control characters and over-length values.
- AC4: A Claude launch for a session carrying both settings includes `--max-budget-usd` and `--fallback-model` with the stored values.
- AC5: A Codex launch for a session carrying both settings includes neither flag and still launches successfully.
- AC6: `cdx configs` shows both settings for every session, and marks them as not applying to Codex sessions.
- AC7: `cdx set --sessions all` and `--provider PROVIDER` apply both settings in bulk exactly as they do for `power`.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: `cdx set <name> --budget 5` then `cdx config <name> --json` reports the stored ceiling, and `cdx unset <name> --budget` removes it.
- request-AC2 -> This backlog slice. Proof: AC2: `--budget 0`, `--budget -1`, `--budget abc` and a value above the accepted maximum are each rejected with an error naming the setting, and nothing is written to the store.
- request-AC3 -> This backlog slice. Proof: AC3: `cdx set <name> --fallback-model <model>` is validated identically to `--model`, including the rejection of control characters and over-length values.
- request-AC13 -> This backlog slice. Proof: AC4: A Claude launch for a session carrying both settings includes `--max-budget-usd` and `--fallback-model` with the stored values.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Primary task(s): `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# AI Context
- Summary: Add budget and fallback-model as pinnable launch settings
- Keywords: scaffolded-backlog, add budget and fallback-model as pinnable launch settings, implementation-ready
- Use when: Implementing the scaffolded slice for Add budget and fallback-model as pinnable launch settings.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
