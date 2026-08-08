## task_040_settle_0_15_0_s_remainder_and_cut_0_15_1 - Settle 0.15.0's remainder and cut 0.15.1
> From version: 0.15.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-09

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Correct the `req_028` record first. It is the smallest item and the one whose being wrong costs the most: every later decision in this repository is made by reading these documents, and one that understates verification teaches the reader to distrust all of them.
- [x] 2. Then the registry lock, because it is a real failure of the product's own use case on a supported platform, and because 0.15.1 should not go out without it. Verify on a physical Windows machine - CI is the environment that hides this, so a green CI proves nothing here.
- [x] 3. Then measure the option layer, and stop there. Publish the classification before choosing a design. The precedent is `req_027`, whose measurement said to stop after two modules when intuition said six, and the more recent one on `provider_runtime`, where measurement showed the intended seam had no helpers of its own.
- [x] 4. Then consolidate, migrating one option at a time with the suite green between each. The test that proves the work is one that adds a throwaway option and demonstrates an incomplete declaration failing loudly.
- [x] 5. Cut 0.15.1 last, carrying the two fixes. Record release evidence only after observing the thing it describes - the checksum, GitHub release and publication gates are only observable after the tag exists.
- [x] 6. Throughout: no runtime dependency, no renamed options, no changed semantics. This request is about making the existing surface hold, not about redesigning it.
- [x] 7. Closeout: state for each criterion whether it was tested or observed, and on which platform. The Windows criteria are only satisfiable by observation on a real machine.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do`
- `item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing`
- `item_070_measure_what_a_single_option_actually_costs_before_designing_anything`
- `item_071_make_an_incomplete_option_declaration_impossible`
- `item_072_cut_0_15_1_once_the_rest_has_settled`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2 -> `item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do`. Proof deferred to slice closeout.
- request-AC3, request-AC4, request-AC5 -> `item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing`. Proof deferred to slice closeout.
- request-AC6 -> `item_070_measure_what_a_single_option_actually_costs_before_designing_anything`. Proof deferred to slice closeout.
- request-AC7, request-AC8, request-AC9, request-AC10 -> `item_071_make_an_incomplete_option_declaration_impossible`. Proof deferred to slice closeout.
- request-AC11 -> `item_072_cut_0_15_1_once_the_rest_has_settled`. Proof deferred to slice closeout.
- request-AC1 -> This task. Proof: **done.** The AC11 record now states the whole sequence - the two identification failures, the discovery that completion is unreadable from agent state, and the end-to-end verification that followed - and reports the criterion as met.
- request-AC2 -> This task. Proof: **observed, and the changelog was already right.** It said 'it works' and attributed the opt-in to limited exposure. The published note was accurate and the corpus was the thing lagging, which is the opposite of the usual failure and worth recording.
- request-AC3 -> This task. Proof: **observed on hardware.** 632 passed, 5 skipped, no failures on the maintainer's Windows machine, including `test_concurrent_starts_do_not_lose_records`, which had failed there on every run since before v0.14.0. CI could not serve as evidence here: it was green throughout while the failure reproduced on a physical desktop.
- request-AC4 -> This task. Proof: **done.** Windows takes `LK_NBLCK` and waits in a loop cdx controls, so a waiter waits as `fcntl.flock` does instead of giving up after ten attempts. The remaining difference - a bounded deadline rather than an indefinite block - is deliberate and documented in the module.
- request-AC5 -> This task. Proof: **tested.** `test_an_exhausted_wait_is_reported_as_contention_not_as_an_oserror` asserts a `CdxError` naming the contention with exit code 75, not a raw `OSError`.
- request-AC6 -> This task. Proof: **done, and it changed the plan.** Ten sites measured against five options of differing shapes: six restate one fact, three encode a real decision (validation rules, value formatting, provider mapping). Recorded in item_070 with `scripts/measure_option_sites.py` to keep it rerunnable. The measurement also found what the count hid - two neighbouring parsers returning by opposite strategies - which is why the answer became a check rather than a consolidation.
- request-AC7 -> This task. Proof: **partially, and deliberately so.** The measurement said generating all nine sites would require expressing validation declaratively, trading one indirection for a worse one. What is delivered is the loudness half: a declared-and-unused option fails the suite. The single-declaration half is not done and is not planned on this evidence.
- request-AC8 -> This task. Proof: **observed.** `cdx schema --json` is unchanged; nothing in this request touched its derivation.
- request-AC9 -> This task. Proof: **observed.** No dependency added; `pyproject.toml` still declares `cryptography` alone.
- request-AC10 -> This task. Proof: **tested.** `test_the_check_catches_the_failover_regression` reproduces the exact shape - a key in the schema and absent from the returned literal - as source, and asserts it is caught. The check took three rounds against real code before it stopped flagging correct parsers, which is recorded in the commit because a test that cries wolf teaches readers to ignore it.
- request-AC11 -> This task. Proof: **observed.** 0.15.1 carries both fixes; npm reports 0.15.1 as latest and `pypi.org/pypi/cdx-manager/0.15.1/json` returns 200. The changelog names what closed from 0.15.0's gaps (Claude's wording) and what did not (personal-plan Codex wording, delegation exposure).

# Validation
- (no validation recorded yet)
- 639 tests on macOS; 632 passed + 5 skipped with no failures on physical Windows hardware. 0.15.1 published to npm and PyPI and verified at both registries.
- Finish workflow executed on 2026-08-09.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-09.
- Linked backlog item(s): `item_068_correct_the_req_028_record_to_state_what_background_delegation_was_actually_verified_to_do`, `item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing`, `item_070_measure_what_a_single_option_actually_costs_before_designing_anything`, `item_071_make_an_incomplete_option_declaration_impossible`, `item_072_cut_0_15_1_once_the_rest_has_settled`
- Related request(s): `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`

# AI Context
- Summary: Settle 0.15.0's remainder and cut 0.15.1
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)
