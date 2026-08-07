## task_033_orchestrate_the_unified_session_selection_ranking - Orchestrate the unified session selection ranking
> From version: 0.13.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Characterize first: build a fixture set of sessions and status rows covering usable, cooling-down, blocked-with-reset, blocked-without-reset, logged-out, disabled, credit-bearing, and priority-tuned cases. Record what each current entry point picks for every fixture, so the refactor has a baseline instead of an intention.
- [ ] 2. Identify from that baseline exactly which fixtures the two rankings already disagree on. Those are the only cases where behavior may legitimately change; every other fixture is a regression guard.
- [ ] 3. Extract the unified ranking, folding in provider filtering, `--priority`, the reasoning-effort floor, tiering, credits, and reset timestamps. Settle the reasoning-effort tie-break and the logged-out candidacy question explicitly, recording the rationale in the code.
- [ ] 4. Route `_select_headless_session`, `recommend_priority_rows`, and `resolve_notify_event`'s next-ready branch through it, one caller at a time, re-running the characterization suite after each so a divergence is attributed to the caller that introduced it.
- [ ] 5. Carry the configured priority into status rows and weigh it in the unified ranking, then settle where priority sits relative to availability and reset tiering — this is the decision that determines whether the setting feels honored.
- [ ] 6. Resolve the `Priority:` naming collision in user-facing output.
- [ ] 7. Return the deciding factor alongside the winner, so the separate reporting work has something truthful to publish.
- [ ] 8. Update the README to document one selection rule, replacing any per-command description.
- [ ] 9. Run the CLI, status-view, and notify test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_047_extract_one_parameterized_session_ranking_used_by_every_selector`
- `item_048_make_the_priority_setting_count_in_next_status_and_ready`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC4, request-AC5, request-AC7 -> `item_047_extract_one_parameterized_session_ranking_used_by_every_selector`. Proof deferred to slice closeout.
- request-AC3, request-AC6, request-AC8 -> `item_048_make_the_priority_setting_count_in_next_status_and_ready`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate the unified session selection ranking
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract`
- Product brief(s): `prod_012_one_session_selection_rule_across_every_command`
- Architecture decision(s): (none yet)
