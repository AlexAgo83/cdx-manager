## task_034_orchestrate_truthful_selection_reporting - Orchestrate truthful selection reporting
> From version: 0.13.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Capture the current `cdx select --json` payload for a few session sets, including one where availability does not decide the winner, so the change can be checked against what callers see today.
- [x] 2. Introduce a single ordered definition of the ranking's factors and build both the sort key and the published policy from it, plus the drift test that keeps them together.
- [x] 3. Have the ranking report which factor first separated the winner from the runner-up, covering the single-candidate case explicitly, and use it for `reason`.
- [x] 4. Add the refresh option to `cdx run` and forward it to the selector, leaving cached status as the default.
- [x] 5. Emit the unknown-availability warning through the run payload's existing warnings channel, and publish its code through `cdx schema --json`.
- [x] 6. Confirm the selected session is unchanged for every captured baseline; this request changes what cdx says about its choice, not the choice.
- [x] 7. Document `selection_policy`, `reason`, the refresh option, and the new warning in the README's programmatic-caller section.
- [x] 8. Run the CLI test file, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_049_derive_the_published_selection_policy_and_reason_from_the_ranking`
- `item_050_let_run_provider_refresh_status_and_warn_when_it_selects_blind`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_049`. Proof: `selection_policy()` is built from `RANKING_FACTORS`, so the published string cannot drift from the applied order.
- request-AC2 -> `item_049`. Proof: `deciding_factor()` names the factor that separated winner from runner-up for that call; `test_single_candidate_reports_no_deciding_factor` covers the case where nothing decided it.
- request-AC3 -> `item_050`. Proof: `cdx run --provider --refresh` requires fresh status before auto-selection, cached remaining the default.
- request-AC4 -> `item_050`. Proof: `session_selected_without_status` (`src/run_command.py:126`) is distinct from a known-low-availability session.
- request-AC5 -> `item_050`. Proof: the code is published in `cdx schema --json` (`src/cli_args.py:481`).
- request-AC6 -> `item_049`, `item_050`. Proof: no exit code or existing field changed meaning; the suite passed unchanged through the delivery commit.
- request-AC7 -> `item_049`. Proof: README describes what the policy and reason mean; the policy is derived, so it is documented as a description rather than a stable identifier.

# Validation
- `npm run lint` and `npm test` (557 tests) clean.
- End-to-end: two codex sessions (80% availability / priority 0, and 40% / priority 90); `cdx select`, `cdx next`, and `cdx status` all name the priority-90 session, and `cdx select` reports `decided on priority`.
- `cdx doctor --check-provider-flags` confirms the claude and codex mappings against the installed CLIs.

# Report
- `selection_policy` is built from `RANKING_FACTORS` and reports ordering factors and candidate filters separately, so it can no longer describe a filter as a sort stage or omit a tie-break. It is now a structured object rather than an underscore-joined string.
- `reason` and the new `deciding_factor` name the factor that actually separated the winner from the runner-up for that call, and report the single-candidate case explicitly instead of naming a factor that decided nothing.
- `cdx run --provider` accepts `--refresh`; cached status stays the default so ordinary runs do not each pay for a provider probe.
- Auto-selection on a session with no recorded availability emits `session_selected_without_status`, distinct from a session known to be low. Named sessions never emit it, since nothing was selected.
- Landed after `req_022` rather than before, so the policy is derived from the unified ranking once instead of from the old headless sort key and then moved.

# AI Context
- Summary: Orchestrate truthful selection reporting
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_023_stop_cdx_select_from_publishing_a_selection_policy_and_reason_it_does_not_follow`
- Product brief(s): `prod_013_truthful_reporting_of_how_a_session_was_selected`
- Architecture decision(s): (none yet)
