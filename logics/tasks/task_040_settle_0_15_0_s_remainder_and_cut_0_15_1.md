## task_040_settle_0_15_0_s_remainder_and_cut_0_15_1 - Settle 0.15.0's remainder and cut 0.15.1
> From version: 0.15.0
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
- [ ] 1. Correct the `req_028` record first. It is the smallest item and the one whose being wrong costs the most: every later decision in this repository is made by reading these documents, and one that understates verification teaches the reader to distrust all of them.
- [ ] 2. Then the registry lock, because it is a real failure of the product's own use case on a supported platform, and because 0.15.1 should not go out without it. Verify on a physical Windows machine - CI is the environment that hides this, so a green CI proves nothing here.
- [ ] 3. Then measure the option layer, and stop there. Publish the classification before choosing a design. The precedent is `req_027`, whose measurement said to stop after two modules when intuition said six, and the more recent one on `provider_runtime`, where measurement showed the intended seam had no helpers of its own.
- [ ] 4. Then consolidate, migrating one option at a time with the suite green between each. The test that proves the work is one that adds a throwaway option and demonstrates an incomplete declaration failing loudly.
- [ ] 5. Cut 0.15.1 last, carrying the two fixes. Record release evidence only after observing the thing it describes - the checksum, GitHub release and publication gates are only observable after the tag exists.
- [ ] 6. Throughout: no runtime dependency, no renamed options, no changed semantics. This request is about making the existing surface hold, not about redesigning it.
- [ ] 7. Closeout: state for each criterion whether it was tested or observed, and on which platform. The Windows criteria are only satisfiable by observation on a real machine.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do`
- `item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing`
- `item_070_measure_what_a_single_option_actually_costs_before_designing_anything`
- `item_071_make_an_incomplete_option_declaration_impossible`
- `item_072_cut_0_15_1_once_the_rest_has_settled`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2 -> `item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do`. Proof deferred to slice closeout.
- request-AC3, request-AC4, request-AC5 -> `item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing`. Proof deferred to slice closeout.
- request-AC6 -> `item_070_measure_what_a_single_option_actually_costs_before_designing_anything`. Proof deferred to slice closeout.
- request-AC7, request-AC8, request-AC9, request-AC10 -> `item_071_make_an_incomplete_option_declaration_impossible`. Proof deferred to slice closeout.
- request-AC11 -> `item_072_cut_0_15_1_once_the_rest_has_settled`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Settle 0.15.0's remainder and cut 0.15.1
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)
