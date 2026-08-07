## task_035_orchestrate_one_source_of_truth_for_accepted_values_and_provider_flags - Orchestrate one source of truth for accepted values and provider flags
> From version: 0.13.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 95%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Map the current state before changing it: for each of the three settings, record which module each entry point validates against and what each copy contains, so any divergence introduced later is attributable.
- [x] 2. Wave 1 - deduplicate: pick the owning module for each value set (avoiding an import cycle), point every validator and the schema at it, and delete the copies. Extend the schema drift test to cover every validator, and add the guard against a duplicate reappearing.
- [x] 3. Wave 2 - close the alias asymmetry: apply `cdx run`'s permission alias normalization in `cdx set` and the `perm` alias command, storing the canonical value. Confirm against the deduplicated definitions from wave 1 rather than adding a fourth list.
- [x] 4. Wave 3 - provider flag check: add the opt-in doctor check, exercising the mapped flags against the installed provider CLI. Build it against a stubbed CLI first so the issue #8 condition is reproducible in tests, then confirm against the real CLIs.
- [x] 5. Verify the user-visible outcome directly: a value accepted by `cdx run` is accepted by `cdx set`, `cdx schema --json` matches what both accept, and the opt-in check reports the current mappings as confirmed on a machine with the provider CLIs installed.
- [x] 6. Update the README for the single source of accepted values, the aliases working in both commands, and the opt-in check.
- [x] 7. Run the CLI, session-service, and health test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_051_collapse_the_duplicated_accepted_value_enums_into_single_definitions`
- `item_052_accept_the_permission_aliases_in_cdx_set_as_well_as_cdx_run`
- `item_053_add_an_opt_in_check_that_mapped_provider_flags_exist_in_the_provider_cli`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC3, request-AC4, request-AC7 -> `item_051_collapse_the_duplicated_accepted_value_enums_into_single_definitions`. Proof deferred to slice closeout.
- request-AC2, request-AC7, request-AC8 -> `item_052_accept_the_permission_aliases_in_cdx_set_as_well_as_cdx_run`. Proof deferred to slice closeout.
- request-AC5, request-AC6, request-AC8 -> `item_053_add_an_opt_in_check_that_mapped_provider_flags_exist_in_the_provider_cli`. Proof deferred to slice closeout.

# Validation
- `npm run lint` and `npm test` (557 tests) clean.
- End-to-end: two codex sessions (80% availability / priority 0, and 40% / priority 90); `cdx select`, `cdx next`, and `cdx status` all name the priority-90 session, and `cdx select` reports `decided on priority`.
- `cdx doctor --check-provider-flags` confirms the claude and codex mappings against the installed CLIs.

# Report
- `config.py` owns the reasoning-effort and permission definitions; it was chosen as the leaf module so the ownership could not introduce an import cycle. Six copies across three modules are gone.
- The drift guard is two tests: one asserts identity rather than equality, so a reintroduced literal that happens to match today still fails; the other scans `src/` and names any module restating one of these sets.
- `cdx set` and the `perm` alias now accept the permission aliases and store the canonical value. Direction confirmed as planned: added to `set` rather than removed from `run`, since removing would break callers passing provider-native spellings.
- The provider flag check reads `LAUNCH_PERMISSION_ARGS`, which meant first moving the antigravity and ollama mappings out of inline branches into that table. Ollama's entry is deliberately empty, which is what lets the check distinguish "nothing to verify" from "not verified".
- Verified against the real CLIs: claude and codex mappings are confirmed accepted today. The issue #8 condition was reproduced by mapping `--experimental-yolo` for codex, which the check fails by name — both as a live check and as a regression test.

# AI Context
- Summary: Orchestrate one source of truth for accepted values and provider flags
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits`
- Product brief(s): `prod_014_one_definition_of_what_cdx_accepts_and_emits`
- Architecture decision(s): (none yet)
