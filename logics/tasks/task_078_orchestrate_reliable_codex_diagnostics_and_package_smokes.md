## task_078_orchestrate_reliable_codex_diagnostics_and_package_smokes - Orchestrate reliable Codex diagnostics and package smokes
> From version: 0.20.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-22 11:59:11

# AI Context
- Summary: Deliver bounded app-server stream handling and package-level doctor checks with controlled local shims.
- Keywords: orchestrate, reliable, codex, diagnostics, package, smokes
- Use when: Coordinating the diagnostic-stream and artifact-smoke slices in this request chain.
- Skip when: Changing authentication flows or performing a release.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace the app-server subprocess streams and test doubles to select the smallest stderr handling change.
- [ ] 2. Add the noisy-stderr regression test and retain timeout and cleanup coverage.
- [ ] 3. Extend package artifact setup with minimal local provider shims and isolated state.
- [ ] 4. Run doctor from the packed npm and wheel installs, then run project and Logics validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_138_drain_codex_app_server_diagnostic_stderr_safely`
- `item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_138_drain_codex_app_server_diagnostic_stderr_safely`. Proof deferred to slice closeout.
- request-AC2 -> `item_138_drain_codex_app_server_diagnostic_stderr_safely`. Proof deferred to slice closeout.
- request-AC3 -> `item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts`. Proof deferred to slice closeout.
- request-AC4 -> `item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_069_harden_codex_probe_process_and_package_smoke_coverage`
- Product brief(s): `prod_052_reliable_codex_diagnostics_in_packaged_installs`
- Architecture decision(s): (none yet)
