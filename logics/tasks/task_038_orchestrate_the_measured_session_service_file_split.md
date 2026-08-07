## task_038_orchestrate_the_measured_session_service_file_split - Orchestrate the measured session service file split
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
- [ ] 1. 1. Re-measure the coupling before starting. The numbers in `item_059` were taken at `req_026` closeout and the file has not been frozen since; both prior requests found that a measurement reused across steps is wrong by the time it is used.
- [ ] 2. 2. Wave 1 - relocate the ten shared helpers to the utility layer in one commit, then confirm the remaining groups share nothing.
- [ ] 3. 3. Wave 2 - extract the status group, facade in place, full suite and interface check.
- [ ] 4. 4. Wave 3 - extract the backup group, add the facade guard test, and record in the code why the other four groups stay.
- [ ] 5. 5. Expect the two `req_025` failure modes and check for them explicitly: pass-through imports stripped by ruff once their last in-file caller leaves, and function-local relative imports resolving one level too shallow inside a subpackage.
- [ ] 6. 6. Confirm the end state: interface unchanged at 29 keys, every prior import still resolving, no caller touched.
- [ ] 7. 7. Run the full suite and `npm run lint`, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] 8. ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] 9. Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] 10. GATE: do not close until lint, audit, and scaffold validation pass.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_060_move_the_shared_helpers_into_a_session_service_utility_layer`
- `item_061_extract_the_status_group_into_its_own_module`
- `item_062_extract_the_backup_group_and_record_why_the_other_groups_stay`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC2, request-AC3, request-AC7 -> `item_060_move_the_shared_helpers_into_a_session_service_utility_layer`. Proof deferred to slice closeout.
- request-AC1, request-AC3, request-AC5, request-AC7, request-AC8 -> `item_061_extract_the_status_group_into_its_own_module`. Proof deferred to slice closeout.
- request-AC1, request-AC4, request-AC6, request-AC7, request-AC8 -> `item_062_extract_the_backup_group_and_record_why_the_other_groups_stay`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate the measured session service file split
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
- Product brief(s): `prod_017_a_session_service_whose_file_boundaries_match_its_real_seams`
- Architecture decision(s): (none yet)
