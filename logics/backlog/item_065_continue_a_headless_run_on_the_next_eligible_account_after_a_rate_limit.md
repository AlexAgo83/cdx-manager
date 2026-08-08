## item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit - Continue a headless run on the next eligible account after a rate limit
> From version: 0.14.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 20%
> Complexity: High
> Theme: Quota-aware execution
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-08

# Problem
- `cdx run` selects a session once and dies with it. A task that hits a rate limit fails even when other registered accounts are at full quota - the exact situation cdx exists to know about.
- There is no rate-limit detection in the codebase. The only retry, `_should_retry_without_transcript`, relaunches without transcript capture after a `script` failure and is unrelated to quota. Detection is the genuinely hard and genuinely new part of this item, and the providers signal exhaustion differently.
- `RunRegistry` records one session per run, so a run that moved between accounts has no representation today and would appear in `cdx runs` as either one misleading row or several unrelated ones.

# Preparation findings
Detection was the open risk when the request was written. It is smaller than it
looked, because both providers already emit structured output on the paths cdx
uses, and because cdx holds a second, independent signal.

- **Codex headless already emits a JSONL event stream.** `src/provider_runtime.py:674` builds `["exec", "--json", "-C", cwd]`, and `codex exec --json` prints events to stdout as JSONL. Detection reads typed events rather than scraping stderr.
- **Claude headless already requests JSON.** `src/provider_runtime.py:654` builds `["--print", "--output-format", "json", ...]`, which yields one structured result at completion. That is sufficient here: failover triggers on termination, not mid-stream. `--output-format stream-json` would only be needed for reacting before the run ends, which this slice does not do - recording that as a deliberate limit avoids an unnecessary change to the headless contract.
- **A second, independent signal already exists.** cdx can refresh the session's own rate-limit status through the existing status pipeline and check whether the account is actually exhausted. Requiring both signals - a terminated run *and* a status that confirms exhaustion - converts the dangerous failure mode (a false positive migrating a healthy run off a working account) into a benign one (a missed failover, which behaves exactly like today).
- Corroboration has a cost worth stating: the Codex status probe spawns `app-server` and can rotate the OAuth token, which is why `CODEX_STATUS_CACHE_TTL_SECONDS` exists. A failover check must force a refresh, so it must be rare - once per termination, never in a loop.
- `rank_sessions` and `selection_policy` (`src/session_ranking.py`) are already shared by `next`, `select`, `status` and `run`, so re-selection needs a caller, not a second ranking. Excluding the exhausted session from the next pass is the only new selection input.
- `RunRegistry.start()` fixes `session` and `provider` on the record and `finish()` closes it (`src/run_registry.py:142,169`). Representing a sequence of occupancies is a registry schema change, and it must land before the loop that would otherwise write runs in a shape the reporting cannot express.
- Neither provider's exhaustion event shape is pinned here on purpose: it is version-specific, it is the part most likely to drift, and the slice isolates it behind one function per provider so a future change is a one-file correction. The verified provider versions are recorded at closeout.

# Scope
- In:
  - Detect provider rate-limit termination for Codex and Claude, distinguished from every other non-zero exit, with the detection isolated behind one function per provider so it can be corrected as the providers change. Read the structured output the headless paths already produce (`codex exec --json` JSONL events; the Claude `--print --output-format json` result), not stderr text.
  - Require corroboration before migrating: a run classified as rate-limited triggers one forced status refresh for that session, and failover proceeds only if the account is confirmed exhausted. Bias every ambiguous case towards not failing over.
  - Extend the run record schema to a sequence of session occupancies **before** implementing the loop, so no run is ever written in a shape the reporting cannot express.
  - Add `--failover` to `cdx run`, re-ranking through the existing `rank_sessions` rather than introducing a second selection path, with the exhausted session excluded from the next pass.
  - Bound the migration: a maximum number of transitions per run, so a systematic misclassification cannot walk a run through every registered account.
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
- AC9: A run classified as rate-limited whose status refresh does not confirm exhaustion does not fail over, and the unconfirmed classification is recorded on the run.
- AC10: A run cannot exceed the configured maximum number of transitions, and hitting that bound is reported distinctly from exhausting the eligible sessions.
- AC11: Detection reads the providers' structured output; a run is never classified from stderr text alone.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: AC1: A run whose provider terminates for a rate-limit reason is classified as rate-limited, and a run that fails for any other reason is not.
- request-AC7 -> This backlog slice. Proof: AC4 and AC5: one `run_id` for the whole task, each occupied session listed in order with its transition reason, and one row in `cdx runs`.
- request-AC8 -> This backlog slice. Proof: AC6 and AC10: exhausting the eligible sessions and hitting the transition bound each terminate with their own code, both distinct from a task failure.
- request-AC13 -> This backlog slice. Proof: the ollama provider is listed out of scope; failover selection runs through `rank_sessions` over Codex and Claude sessions only.

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
