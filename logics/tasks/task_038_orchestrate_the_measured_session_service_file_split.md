## task_038_orchestrate_the_measured_session_service_file_split - Orchestrate the measured session service file split
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Re-measure the coupling before starting. The numbers in `item_059` were taken at `req_026` closeout and the file has not been frozen since; both prior requests found that a measurement reused across steps is wrong by the time it is used.
- [x] 2. Wave 1 - relocate the ten shared helpers to the utility layer in one commit, then confirm the remaining groups share nothing.
- [x] 3. Wave 2 - extract the status group, facade in place, full suite and interface check.
- [x] 4. Wave 3 - extract the backup group, add the facade guard test, and record in the code why the other four groups stay.
- [x] 5. Expect the two `req_025` failure modes and check for them explicitly: pass-through imports stripped by ruff once their last in-file caller leaves, and function-local relative imports resolving one level too shallow inside a subpackage.
- [x] 6. Confirm the end state: interface unchanged at 29 keys, every prior import still resolving, no caller touched.
- [x] 7. Run the full suite and `npm run lint`, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] 8. ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] 9. Keep commit creation under operator control; do not force one commit per micro-step.
- [x] 10. GATE: do not close until lint, audit, and scaffold validation pass.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_060_move_the_shared_helpers_into_a_session_service_utility_layer`
- `item_061_extract_the_status_group_into_its_own_module`
- `item_062_extract_the_backup_group_and_record_why_the_other_groups_stay`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_061`, `item_062`. Proof: `src/session_status.py` (23 functions, 4 constants) and `src/session_backup.py` (11 functions, 1 constant), each with the helpers reached only from its group.
- request-AC2 -> `item_060`. Proof: the ten shared helpers plus two cross-group store accessors live in `src/session_helpers.py`; neither new module imports `session_service`.
- request-AC3 -> `item_060`, `item_061`, `item_062`. Proof: `session_service` re-exports every moved name; `src/__init__.py` and all tests import unchanged.
- request-AC4 -> `item_062`. Proof: `test_session_service_facade_still_exposes_every_name_its_callers_import`, covering import statements and `mock.patch` string targets. Verified to fail when one re-export is removed.
- request-AC5 -> `item_060`, `item_061`, `item_062`. Proof: the returned dict was diffed against a pre-request build after each extraction - 29 keys, identical.
- request-AC6 -> `item_062`. Proof: the coupling table is in `session_service`'s docstring, and `test_only_the_measured_seams_were_split_out` fails if a runtime or auth module appears.
- request-AC7 -> `item_060`, `item_061`, `item_062`. Proof: four commits, full suite green after each.
- request-AC8 -> `item_061`. Proof: `src/cli.py` untouched; the only test change is two `mock.patch` targets repointed to `src.session_status`, recorded with its reason.

# Validation
- `npm run lint` clean and the full suite green after each of the four commits (561 tests, 563 after the two guards).
- Service interface diffed against a pre-request build after every extraction: 29 keys, identical.
- Both guard tests verified to fail when violated, not merely observed passing.

# Report
- `session_service.py` went 1690 -> 753 lines. `session_helpers` 179, `session_status` 534, `session_backup` 343.
- The interface is unchanged at 29 keys and `src/cli.py` was never touched. One test file changed: two `mock.patch` targets.
- The measurement that scoped this request had a blind spot - it counted helpers but not calls into another group's entry points. Three such calls existed and both extracted groups had one, so the first slice needed a second commit. Recorded in `item_060`.
- Across `req_025`, `req_026` and `req_027` the same failure keeps recurring in new clothes: a measurement taken once, or taken narrowly, is wrong by the time it is used. Transitive not direct; re-taken between steps, not at the start; entry points as well as helpers.

# AI Context
- Summary: Orchestrate the measured session service file split
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
- Product brief(s): `prod_017_a_session_service_whose_file_boundaries_match_its_real_seams`
- Architecture decision(s): (none yet)
