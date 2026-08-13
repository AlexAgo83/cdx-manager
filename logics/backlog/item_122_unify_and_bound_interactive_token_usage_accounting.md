## item_122_unify_and_bound_interactive_token_usage_accounting - Unify and bound interactive token usage accounting
> From version: 0.19.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 90%
> Complexity: Medium
> Theme: Usage observability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:02

# AI Context
- Summary: Preserve cached usage consistently while keeping transcript accounting bounded and fail-open.
- Keywords: unify, bound, interactive, token, usage, accounting
- Use when: Changing history, stats, normalized usage, or interactive transcript readers.
- Skip when: Building billing telemetry or a new analytics surface.

# Problem
- Interactive records carry cached_input_tokens while shared usage and stats omit it.
- Best-effort transcript accounting can scan and read unbounded provider history at interactive process exit.

# Scope
- In:
  - Add optional cached input tokens to the shared normalized usage schema, JSON history, statistics aggregation, rendering, and tests.
  - Preserve provider-reported totals without adding cached input into them.
  - Constrain transcript candidate discovery and reading with an explicit safe budget and unavailable result.
- Out:
  - A cloud billing estimate or new reporting command.
  - Treating undocumented provider transcript schemas as stable APIs.

# Acceptance criteria
- cdx history and cdx stats JSON preserve cached_input_tokens when supplied without changing total_tokens.
- Interactive accounting does not delay or fail a provider exit when transcript discovery exceeds its configured safe bound.
- Malformed, oversized, or unavailable transcript data remains fail-open and is tested.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: cdx history and cdx stats JSON preserve cached_input_tokens when supplied without changing total_tokens.
- request-AC6 -> This backlog slice. Proof: Interactive accounting does not delay or fail a provider exit when transcript discovery exceeds its configured safe bound.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Primary task(s): `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
