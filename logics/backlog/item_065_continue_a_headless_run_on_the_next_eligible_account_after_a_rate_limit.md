## item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit - Continue a headless run on the next eligible account after a rate limit
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Quota-aware execution
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `cdx run` selects a session once and dies with it. A task that hits a rate limit fails even when other registered accounts are at full quota - the exact situation cdx exists to know about.
- There is no rate-limit detection in the codebase. The only retry, `_should_retry_without_transcript`, relaunches without transcript capture after a `script` failure and is unrelated to quota. Detection is the genuinely hard and genuinely new part of this item, and the providers signal exhaustion differently.
- `RunRegistry` records one session per run, so a run that moved between accounts has no representation today and would appear in `cdx runs` as either one misleading row or several unrelated ones.

# Scope
- In:
  - Detect provider rate-limit termination for Codex and Claude, distinguished from every other non-zero exit, with the detection isolated behind one function per provider so it can be corrected as the providers change.
  - Add `--failover` to `cdx run`, re-ranking through the existing `rank_sessions` rather than introducing a second selection path.
  - Transfer the working context to the newly selected session, using the identity anchor from the session-identity item where available.
  - Extend the run record to represent a sequence of session occupancies with a reason per transition, keeping one `run_id` for the whole task.
  - Report the sequence through `cdx run-report --json` and keep `cdx runs` showing one row per task.
  - Add a specific terminal error code for exhausting every eligible session, distinct from the task itself failing.
- Out:
  - Failover for interactive launches.
  - Resuming the provider conversation across the boundary; the continuation carries transferred context, and what is guaranteed about partial work is stated rather than assumed.
  - Any change to the ollama provider.

# Acceptance criteria
- AC1: A run whose provider terminates for a rate-limit reason is classified as rate-limited, and a run that fails for any other reason is not.
- AC2: `cdx run --failover` continues on the next eligible session, chosen by the same ranking `cdx next` uses.
- AC3: The continuation receives the working context from the session it replaced.
- AC4: The whole task keeps one `run_id`, and `cdx run-report <run_id> --json` lists each session occupied in order with the reason for each transition.
- AC5: `cdx runs` shows one row for a run that failed over, not one per session.
- AC6: With no eligible session left, the run ends with a specific error code naming what was attempted, distinct from a task failure.
- AC7: Without `--failover`, `cdx run` behaves exactly as it does today, including on a rate-limited termination.
- AC8: A disabled session is never selected as a failover target.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: AC1: A run whose provider terminates for a rate-limit reason is classified as rate-limited, and a run that fails for any other reason is not.
- request-AC7 -> This backlog slice. Proof: AC2: `cdx run --failover` continues on the next eligible session, chosen by the same ranking `cdx next` uses.
- request-AC8 -> This backlog slice. Proof: AC3: The continuation receives the working context from the session it replaced.
- request-AC13 -> This backlog slice. Proof: AC4: The whole task keeps one `run_id`, and `cdx run-report <run_id> --json` lists each session occupied in order with the reason for each transition.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Primary task(s): `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`

# AI Context
- Summary: Continue a headless run on the next eligible account after a rate limit
- Keywords: scaffolded-backlog, continue a headless run on the next eligible account after a rate limit, implementation-ready
- Use when: Implementing the scaffolded slice for Continue a headless run on the next eligible account after a rate limit.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
