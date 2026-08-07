## item_047_extract_one_parameterized_session_ranking_used_by_every_selector - Extract one parameterized session ranking used by every selector
> From version: 0.13.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Session selection
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `_select_headless_session` and `_recommend_priority_sessions` each implement a full ranking, with different inputs, different tie-breaks, and different candidate filtering.
- Each has something the other lacks: the headless path filters by provider and honors `--priority`; the recommendation path understands credits, reset timestamps, and the difference between 'blocked with a known reset' and 'blocked with no information'.
- Any future selection rule has to be written twice or it silently applies to only half the commands.

# Scope
- In:
  - Define one ranking function taking the candidate sessions, their status rows, and an options object covering at minimum: provider filter, whether readiness is required, and a minimum reasoning effort.
  - Fold in the tiering, credits, and reset-timestamp handling from the recommendation path and the provider filter, `--priority`, and reasoning-effort floor from the headless path.
  - Settle the reasoning-effort tie-break deliberately, record the choice and its rationale in the code, and make the direction visible rather than implied by a sign in a tuple.
  - Align candidate filtering: decide once whether a logged-out session is ever a candidate, and apply that decision to both entry points instead of only when `require_ready` happens to be set.
  - Route `_select_headless_session`, `recommend_priority_rows`, and `resolve_notify_event`'s next-ready branch through the shared function.
  - Return enough structure alongside the winner for a caller to report which factor decided it, so this item can serve the reporting work tracked separately.
  - Add a characterization test suite over representative session sets, asserting the unified result matches today's behavior wherever the two rankings already agreed.
- Out:
  - No new ranking inputs beyond what the two current implementations already use.
  - No change to the shape of status rows.
  - No change to command-line surfaces in this slice.

# Acceptance criteria
- Given the same sessions and status rows, `cdx select --provider P`, `cdx run --provider P`, and the recommendation shown by `cdx next` name the same session whenever the constraints are equivalent.
- Given a set where both current implementations already agree on the winner, the unified ranking returns that same winner.
- Given a session with a known future reset and one with no reset information, the unified ranking preserves the recommendation path's tiering rather than flattening both to 'unavailable'.
- Given two sessions equal on every other factor and differing only in configured reasoning effort, the documented tie-break direction is applied and asserted by a test that names the expected winner.
- Given a logged-out session, whether it is a candidate is the same for `cdx select`, `cdx run --provider`, and `cdx next`.
- Only one function in the codebase orders sessions by desirability; a test or a grep-backed assertion prevents a second ranking from reappearing.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given the same sessions and status rows, `cdx select --provider P`, `cdx run --provider P`, and the recommendation shown by `cdx next` name the same session whenever the constraints are equivalent.
- request-AC2 -> This backlog slice. Proof: Given a set where both current implementations already agree on the winner, the unified ranking returns that same winner.
- request-AC4 -> This backlog slice. Proof: Given a session with a known future reset and one with no reset information, the unified ranking preserves the recommendation path's tiering rather than flattening both to 'unavailable'.
- request-AC5 -> This backlog slice. Proof: Given two sessions equal on every other factor and differing only in configured reasoning effort, the documented tie-break direction is applied and asserted by a test that names the expected winner.
- request-AC7 -> This backlog slice. Proof: Given a logged-out session, whether it is a candidate is the same for `cdx select`, `cdx run --provider`, and `cdx next`.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_012_one_session_selection_rule_across_every_command`
- Architecture decision(s): (none yet)
- Request: `req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract`
- Primary task(s): `task_033_orchestrate_the_unified_session_selection_ranking`

# AI Context
- Summary: Extract one parameterized session ranking used by every selector
- Keywords: scaffolded-backlog, extract one parameterized session ranking used by every selector, implementation-ready
- Use when: Implementing the scaffolded slice for Extract one parameterized session ranking used by every selector.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
