## task_071_orchestrate_repository_reliability_and_release_contract_hardening - Orchestrate repository reliability and release-contract hardening
> From version: 0.19.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 95%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:02
> Owner: codex

# AI Context
- Summary: Coordinate six independent hardening slices while preserving release and CLI contracts.
- Keywords: orchestrate, repository, reliability, release, contract, hardening
- Use when: Delivering the full repository-reliability request chain.
- Skip when: A single slice can be implemented independently.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Establish CI and artifact verification gates before changing release workflows.
- [x] 2. Harden detached-run registry durability and lock timeout semantics with focused tests.
- [x] 3. Unify usage accounting fields and bound interactive transcript work without changing totals.
- [x] 4. Close measured test gaps, then extract only the seams demonstrated by those tests.
- [x] 5. Update contributor and Logics workflow records, run project and Logics validation, and close out with evidence.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_119_run_tray_tests_and_macos_validation_in_continuous_integration`
- `item_120_verify_installable_package_artifacts_before_release`
- `item_121_make_detached_run_registry_persistence_durable_and_bounded`
- `item_122_unify_and_bound_interactive_token_usage_accounting`
- `item_123_cover_operational_command_boundaries_and_extract_measured_seams`
- `item_124_restore_contributor_and_logics_workflow_signal_accuracy`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_119_run_tray_tests_and_macos_validation_in_continuous_integration`. Proof deferred to slice closeout.
- request-AC7 -> `item_119_run_tray_tests_and_macos_validation_in_continuous_integration`. Proof deferred to slice closeout.
- request-AC2 -> `item_120_verify_installable_package_artifacts_before_release`. Proof deferred to slice closeout.
- request-AC3 -> `item_120_verify_installable_package_artifacts_before_release`. Proof deferred to slice closeout.
- request-AC4 -> `item_121_make_detached_run_registry_persistence_durable_and_bounded`. Proof deferred to slice closeout.
- request-AC5 -> `item_122_unify_and_bound_interactive_token_usage_accounting`. Proof deferred to slice closeout.
- request-AC6 -> `item_122_unify_and_bound_interactive_token_usage_accounting`. Proof deferred to slice closeout.
- request-AC7 -> `item_123_cover_operational_command_boundaries_and_extract_measured_seams`. Proof deferred to slice closeout.
- request-AC8 -> `item_123_cover_operational_command_boundaries_and_extract_measured_seams`. Proof deferred to slice closeout.
- request-AC9 -> `item_124_restore_contributor_and_logics_workflow_signal_accuracy`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
