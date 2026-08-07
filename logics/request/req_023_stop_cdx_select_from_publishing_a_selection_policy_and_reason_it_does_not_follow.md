## req_023_stop_cdx_select_from_publishing_a_selection_policy_and_reason_it_does_not_follow - Stop cdx select from publishing a selection policy and reason it does not follow
> From version: 0.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Session selection
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Needs
- `cdx select --json` publishes a `selection_policy` string and a `reason` string that describe how the session was chosen. Both are hardcoded and neither matches what the code does, so a programmatic caller reading them is misinformed.
- `cdx run --provider` picks a session from status data that may never have been fetched, with no way to ask for fresh data and no signal that the decision rested on unknown values.
- Both are the same failure the `warnings` channel and `cdx schema --json` were just introduced to close: cdx stating something about itself that is written by hand and therefore free to drift from what it actually does.

# Context
- `handle_select` sets `policy = "ready_then_cooldown_then_health_then_priority_then_name"` (`src/cli_commands.py:858`) as a literal. The real sort key in `_select_headless_session` (`src/cli_commands.py:1571`) is `(-cooldown, -available_pct, -priority, reasoning_rank, name)`. The reasoning-effort term is absent from the published string entirely, and `ready` is not a sort stage at all — it is a candidate filter, applied only when `--require-ready` is passed.
- `reason = "highest availability suitable session"` (`src/cli_commands.py:873`) is likewise a literal, returned unchanged whether availability actually decided the outcome or whether the winner was settled on priority, reasoning effort, or alphabetical order.
- `handle_run` calls the selector with `force_refresh=False` hardcoded (`src/cli_commands.py:1248`). `cdx select` exposes `--refresh`; `cdx run --provider` exposes no equivalent.
- Relationship to `req_022`: that request unifies the two rankings; this one only fixes what cdx *says* about the ranking it has. Both orders work. Done first, this request derives its policy string and deciding factor from today's headless sort key, and `req_022` moves them when it replaces that key — the drift test added here is what makes the move safe. Done second, `req_022` will already have exposed the deciding factor and this request only has to publish it. Neither blocks the other, and this one is deliberately the smaller, shippable half.
- A session whose status was never recorded has `available_pct` of `None`, which the selector maps to `-1.0`. It therefore sorts behind a session sitting at one percent of its quota. On a freshly imported or long-idle set of sessions this is the normal case, not an edge case, and nothing in the payload distinguishes 'lowest availability' from 'availability unknown'.
- The run payload now has a populated `warnings` list and cdx publishes `cdx schema --json`, so there is an established channel for reporting a degraded decision and an established expectation that published contract strings are derived rather than typed.

# Acceptance criteria
- AC1: The `selection_policy` reported by `cdx select` is derived from the ranking the code actually applies, so a change to the sort order changes the published string without anyone editing it, and a test fails if the two can disagree.
- AC2: The `reason` reported by `cdx select` names the factor that actually decided the winner for that call, rather than a fixed sentence.
- AC3: `cdx run --provider` accepts a refresh option so a caller can require fresh status before auto-selection, with the current cached behavior remaining the default.
- AC4: When auto-selection picks a session whose availability is unknown, the payload carries a warning saying the decision was made without status data, distinct from a session known to be at low availability.
- AC5: `cdx schema --json` lists any new warning codes introduced here, consistent with it already publishing the existing ones.
- AC6: Existing successful behavior is unchanged: the same session is selected as before for the same inputs, and no exit code or existing field changes meaning.
- AC7: The README describes what `selection_policy` and `reason` mean and warns callers not to parse the policy string as a stable identifier if it is derived.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_013_truthful_reporting_of_how_a_session_was_selected`
- Architecture decision(s): (none yet)

# References
- src/cli_commands.py
- src/cli_args.py
- src/run_command.py
- README.md
- test/test_cli_py.py

# AI Context
- Summary: Stop cdx select from publishing a selection policy and reason it does not follow
- Keywords: request-chain-scaffold, stop cdx select from publishing a selection policy and reason it does not follow, development-ready
- Use when: You need to implement or review the scaffolded workflow for Stop cdx select from publishing a selection policy and reason it does not follow.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_049_derive_the_published_selection_policy_and_reason_from_the_ranking`
- `item_050_let_run_provider_refresh_status_and_warn_when_it_selects_blind`
