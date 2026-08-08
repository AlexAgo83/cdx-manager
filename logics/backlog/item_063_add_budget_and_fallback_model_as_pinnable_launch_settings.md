## item_063_add_budget_and_fallback_model_as_pinnable_launch_settings - Add budget and fallback-model as pinnable launch settings
> From version: 0.14.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 85%
> Complexity: Low
> Theme: Quota-aware execution
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-08
> Owner: claude

# Problem
- Claude Code 2.1.226 ships `--max-budget-usd` and `--fallback-model`; cdx maps neither, so a user who wants either must launch the provider outside cdx and lose account isolation.
- A spend ceiling is the natural companion to quota routing and cdx cannot express it: `cdx stats` measures spend after the fact and nothing can cap it.
- `--fallback-model` is the provider's own in-process answer to unavailability, which makes it both immediately useful and a useful reference point for the cross-account failover this request builds later.

# Preparation findings
Read from the installed CLI (Claude Code 2.1.226), not from memory. Two of these
contradict the request's first reading and narrow this slice.

- **Both flags are `--print`-only.** `claude --help` states "(only works with --print)" for `--max-budget-usd` and for `--fallback-model`. They therefore apply to the headless path alone, not to interactive launches and not to resume. This is the main correction: the slice maps them in one place, not three.
- The headless Claude spec is already built at `src/provider_runtime.py:654` as `["--print", "--output-format", "json", "--name", session["name"]]`. That is the single insertion point.
- The interactive spec (`src/provider_runtime.py:486`) and the resume spec (`src/provider_runtime.py:598`) must **not** receive these flags; passing them there would be rejected by the provider.
- **`--fallback-model` accepts a comma-separated list**, tried in order, re-trying the primary at the start of each user turn. Validating it "identically to `--model`" would wrongly reject a list, so validation accepts a comma-separated sequence and validates each element.
- Codex has no equivalent for either flag: `codex --help` and `codex exec --help` expose neither a budget ceiling nor a model fallback. The Codex asymmetry stands as scaffolded.
- `rtk` is the reference implementation for the touch-point set; `model` (string) and `priority` (bounded number) are the reference validators.

# Scope
- In:
  - Add `budget` and `fallback_model` to `_normalize_launch_settings` in `src/session_service.py` (around the existing `model` and `priority` blocks), with `budget` rejecting non-numeric, non-positive, NaN and infinite values against a `MAX_LAUNCH_BUDGET_USD` bound whose only job is catching a misplaced decimal.
  - Validate `fallback_model` as a comma-separated sequence, applying the existing `MAX_LAUNCH_MODEL_LENGTH` and control-character rules to each element, and rejecting empty elements.
  - Add both keys to the allowed set in `unset_launch_settings` (`src/session_service.py:313`).
  - Add the `--budget` and `--fallback-model` options to the `cdx set` and `cdx unset` tables in `src/cli_args.py` (the `--model`/`--priority` entries near lines 236, 256, 276 and 295 are the template).
  - Add both to the display list in `src/cli_helpers.py:487` and to `_format_launch_configs` in `src/commands/status.py:110`.
  - Map both **only** into the headless Claude spec at `src/provider_runtime.py:654`, leaving the interactive spec (line 486) and the resume spec (line 598) untouched.
  - Report in `cdx configs` that both settings apply to headless Claude runs only, so a user who pins them on a Codex session, or expects them on an interactive launch, is told rather than left guessing.
- Out:
  - Any shortcut command of the form `cdx budget <name> <value>`, which can follow once the settings exist.
  - Enforcing the budget inside cdx; the ceiling is the provider's to apply.
  - Verifying that the fallback models named by the user exist; that is the provider's to reject.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: `cdx set <name> --budget 5` then `cdx config <name> --json` reports the stored ceiling, and `cdx unset <name> --budget` removes it.
- AC2: `--budget 0`, `--budget -1`, `--budget abc` and a value above the accepted maximum are each rejected with an error naming the setting, and nothing is written to the store.
- AC3: `cdx set <name> --fallback-model <model>` accepts both a single model and a comma-separated list, applies the `--model` character and length rules to each element, and rejects an empty element.
- AC4: A headless Claude run (`cdx run`) for a session carrying both settings includes `--max-budget-usd` and `--fallback-model` with the stored values.
- AC5: An interactive Claude launch and a Claude resume for the same session include neither flag, because the provider accepts them only with `--print`.
- AC6: A Codex launch for a session carrying both settings includes neither flag and still launches successfully.
- AC7: `cdx configs` shows both settings for every session and states that they apply to headless Claude runs only.
- AC8: `cdx set --sessions all` and `--provider PROVIDER` apply both settings in bulk exactly as they do for `power`.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: `cdx set <name> --budget 5` then `cdx config <name> --json` reports the stored ceiling, and `cdx unset <name> --budget` removes it.
- request-AC2 -> This backlog slice. Proof: AC2: `--budget 0`, `--budget -1`, `--budget abc` and a value above the accepted maximum are each rejected with an error naming the setting, and nothing is written to the store.
- request-AC3 -> This backlog slice. Proof: AC4, AC5 and AC6 together: the flags appear on a headless Claude run and on nothing else, which is the provider's `--print`-only constraint made observable; AC7 covers reporting it in `cdx configs`.
- request-AC13 -> This backlog slice. Proof: the ollama provider is listed out of scope, and no scope-in item touches provider dispatch for it.

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
