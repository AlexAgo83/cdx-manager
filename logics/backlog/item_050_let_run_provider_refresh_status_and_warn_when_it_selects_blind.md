## item_050_let_run_provider_refresh_status_and_warn_when_it_selects_blind - Let run --provider refresh status and warn when it selects blind
> From version: 0.13.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Session selection
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `handle_run` hardcodes `force_refresh=False`, so `cdx run --provider` cannot be told to fetch fresh status before choosing, while `cdx select` can.
- A session with no recorded `available_pct` is mapped to `-1.0` and sorts behind a session at one percent. The payload gives no hint that the ranking ran on absent data.
- On a freshly imported or long-idle set of sessions this is the ordinary case, so an auto-selected run can quietly land on a session chosen by alphabetical fallback.

# Scope
- In:
  - Add a refresh option to `cdx run` that forwards to the selector's `force_refresh`, keeping cached status as the default so ordinary runs do not each pay for a provider probe.
  - Emit a warning on the run payload when the selected session's availability was unknown at selection time, naming the session and stating that the choice was made without status data.
  - Keep that warning distinct from a session known to be at low availability, which is a different situation and not a degradation.
  - Publish the new warning code through `cdx schema --json` alongside the existing ones.
  - Document the option and the warning in the README's programmatic-caller section.
  - Add tests for the refresh option reaching the selector, the warning firing on unknown availability, and its absence when availability is known — including when it is known to be low.
- Out:
  - No refresh by default.
  - No refresh option on commands that do not select a session.
  - No change to the ranking's treatment of unknown availability, only to what is reported about it.

# Acceptance criteria
- Given `cdx run --provider P` with the refresh option, the selector is invoked with refreshed status; without it, cached status is used exactly as today.
- Given an auto-selected session whose `available_pct` was unknown, the run payload carries a warning naming that session and stating the selection ran without status data.
- Given an auto-selected session with a known low availability, no such warning is emitted.
- Given a session named explicitly rather than auto-selected, no selection warning is emitted regardless of status.
- `cdx schema --json` lists the new warning code.
- Exit codes and every existing payload field keep their current meaning.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: Given `cdx run --provider P` with the refresh option, the selector is invoked with refreshed status; without it, cached status is used exactly as today.
- request-AC4 -> This backlog slice. Proof: Given an auto-selected session whose `available_pct` was unknown, the run payload carries a warning naming that session and stating the selection ran without status data.
- request-AC5 -> This backlog slice. Proof: Given an auto-selected session with a known low availability, no such warning is emitted.
- request-AC6 -> This backlog slice. Proof: Given a session named explicitly rather than auto-selected, no selection warning is emitted regardless of status.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_013_truthful_reporting_of_how_a_session_was_selected`
- Architecture decision(s): (none yet)
- Request: `req_023_stop_cdx_select_from_publishing_a_selection_policy_and_reason_it_does_not_follow`
- Primary task(s): `task_034_orchestrate_truthful_selection_reporting`

# AI Context
- Summary: Let run --provider refresh status and warn when it selects blind
- Keywords: scaffolded-backlog, let run --provider refresh status and warn when it selects blind, implementation-ready
- Use when: Implementing the scaffolded slice for Let run --provider refresh status and warn when it selects blind.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
