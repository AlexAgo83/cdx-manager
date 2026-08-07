## task_037_orchestrate_the_session_service_decomposition - Orchestrate the session service decomposition
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Do not start before `req_025`'s pilot has reported. Two structural changes in flight over the same test suite make an attribution problem out of any regression.
- [ ] 2. Measure first: for each of the 46 closures, list exactly which factory locals it references. The split between capture-nothing and capture-something drives both slices and cannot be eyeballed.
- [ ] 3. Wave 1 - lift the closures that capture nothing to module level, one small commit at a time, interface untouched.
- [ ] 4. Wave 2 - work through the state-dependent closures by concern cluster, passing dependencies explicitly, leaving the factory as assembly. Full suite after each commit.
- [ ] 5. Confirm the interface is byte-for-byte the same contract: same keys, same behavior, no caller touched.
- [ ] 6. Wave 3 - measure the coupling between concern groups and decide whether a file split is warranted, recording the evidence either way.
- [ ] 7. Run the full suite and `npm run lint`, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_057_lift_the_closures_that_capture_nothing_into_module_level_functions`
- `item_058_give_the_state_dependent_closures_explicit_dependencies`
- `item_059_decide_the_file_split_from_the_seams_the_decomposition_exposed`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC5 -> `item_057_lift_the_closures_that_capture_nothing_into_module_level_functions`. Proof deferred to slice closeout.
- request-AC1, request-AC3, request-AC4, request-AC5, request-AC7 -> `item_058_give_the_state_dependent_closures_explicit_dependencies`. Proof deferred to slice closeout.
- request-AC6 -> `item_059_decide_the_file_split_from_the_seams_the_decomposition_exposed`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate the session service decomposition
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_026_break_up_the_1153_line_session_service_factory_before_splitting_its_file`
- Product brief(s): `prod_016_a_session_service_that_can_be_read_in_pieces`
- Architecture decision(s): (none yet)
