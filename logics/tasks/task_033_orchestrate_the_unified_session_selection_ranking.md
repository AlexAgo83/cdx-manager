## task_033_orchestrate_the_unified_session_selection_ranking - Orchestrate the unified session selection ranking
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
- [x] 1. Characterize first: build a fixture set of sessions and status rows covering usable, cooling-down, blocked-with-reset, blocked-without-reset, logged-out, disabled, credit-bearing, and priority-tuned cases. Record what each current entry point picks for every fixture, so the refactor has a baseline instead of an intention.
- [x] 2. Identify from that baseline exactly which fixtures the two rankings already disagree on. Those are the only cases where behavior may legitimately change; every other fixture is a regression guard.
- [x] 3. Extract the unified ranking, folding in provider filtering, `--priority`, the reasoning-effort floor, tiering, credits, and reset timestamps. Settle the reasoning-effort tie-break and the logged-out candidacy question explicitly, recording the rationale in the code.
- [x] 4. Route `_select_headless_session`, `recommend_priority_rows`, and `resolve_notify_event`'s next-ready branch through it, one caller at a time, re-running the characterization suite after each so a divergence is attributed to the caller that introduced it.
- [x] 5. Carry the configured priority into status rows and weigh it in the unified ranking, then settle where priority sits relative to availability and reset tiering — this is the decision that determines whether the setting feels honored.
- [x] 6. Resolve the `Priority:` naming collision in user-facing output.
- [x] 7. Return the deciding factor alongside the winner, so the separate reporting work has something truthful to publish.
- [x] 8. Update the README to document one selection rule, replacing any per-command description.
- [x] 9. Run the CLI, status-view, and notify test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_047_extract_one_parameterized_session_ranking_used_by_every_selector`
- `item_048_make_the_priority_setting_count_in_next_status_and_ready`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_047`. Proof: `src/session_ranking.py` holds one parameterized ranking; every selector routes through it.
- request-AC2 -> `item_047`. Proof: the provider filter, `--priority`, credits, reset scheduling and tiering all survive in `RANKING_FACTORS`; the characterisation tests caught three places where a naive merge would have dropped or inverted one.
- request-AC3 -> `item_048`. Proof: `test_priority_orders_two_otherwise_equal_sessions` and `test_next_uses_same_priority_recommendation_as_status`.
- request-AC4 -> `item_047`. Proof: `test_every_selector_agrees_on_the_best_session` asserts agreement across selectors directly rather than per command.
- request-AC5 -> `item_047`. Proof: the reasoning-effort tie-break is an explicit factor with an entry in `FACTOR_DESCRIPTIONS`; `test_lower_reasoning_effort_wins_a_tie` pins its direction.
- request-AC6 -> `item_048`. Proof: the factor names distinguish the user-set `--priority` from the recommendation ordering.
- request-AC7 -> `item_047`. Proof: the characterisation suite ran against the old behaviour first; the three disagreements it surfaced were resolved deliberately and recorded, not absorbed silently.
- request-AC8 -> `item_048`. Proof: README documents `--priority` as a tie-breaker applied after readiness and availability.

# Validation
- `npm run lint` and `npm test` (557 tests) clean.
- End-to-end: two codex sessions (80% availability / priority 0, and 40% / priority 90); `cdx select`, `cdx next`, and `cdx status` all name the priority-90 session, and `cdx select` reports `decided on priority`.
- `cdx doctor --check-provider-flags` confirms the claude and codex mappings against the installed CLIs.

# Report
- Both rankings merged into `src/session_ranking.py`; `_select_headless_session`, `recommend_priority_rows`, and `resolve_notify_event` all call `rank_sessions`. The two superseded implementations are deleted, along with four helpers in `cli_commands` they left dead.
- Characterization surfaced three real divergences the plan existed to catch. Two were preserved, one was resolved deliberately:
  - The recommendation ranking preferred sessions *without* credits (spend included quota before paid credits). A first pass inverted it; the existing test caught it and the preference is kept, with the factor commented so the orientation is not re-guessed.
  - Its factor order depended on the usability class: for a usable session credits and availability came first, for a blocked one the reset time did. The unified ranking keeps that split rather than flattening to one order.
  - It sorted session names descending, as a side effect of reversing the whole sort tuple, disagreeing with the headless ranking's ascending order. Ascending is kept; one test expectation updated.
- Decisions taken where the corpus deliberately left them open: `--priority` ranks within a usability class and not across it, and the reasoning-effort tie-break keeps preferring the weaker session, now stated in code rather than implied by an un-negated sort term.
- Behavior change worth calling out: `--priority` now outranks availability, where it previously sat below it and so only broke exact ties. This is what makes the setting meaningful, and it does change which session existing `cdx select`/`cdx run --provider` calls pick.
- Logged-out sessions are now never candidates; `cdx select` without `--require-ready` could previously return one.

# AI Context
- Summary: Orchestrate the unified session selection ranking
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract`
- Product brief(s): `prod_012_one_session_selection_rule_across_every_command`
- Architecture decision(s): (none yet)
