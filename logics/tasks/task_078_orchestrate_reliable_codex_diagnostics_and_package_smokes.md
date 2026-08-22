## task_078_orchestrate_reliable_codex_diagnostics_and_package_smokes - Orchestrate reliable Codex diagnostics and package smokes
> From version: 0.20.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-22 14:15:48
> Owner: Codex

# AI Context
- Summary: Deliver bounded app-server stream handling and package-level doctor checks with controlled local shims.
- Keywords: orchestrate, reliable, codex, diagnostics, package, smokes
- Use when: Coordinating the diagnostic-stream and artifact-smoke slices in this request chain.
- Skip when: Changing authentication flows or performing a release.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace the app-server subprocess streams and test doubles to select the smallest stderr handling change.
- [x] 2. Add the noisy-stderr regression test and retain timeout and cleanup coverage.
- [x] 3. Extend package artifact setup with minimal local provider shims and isolated state.
- [x] 4. Run doctor from the packed npm and wheel installs, then run project and Logics validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_138_drain_codex_app_server_diagnostic_stderr_safely`
- `item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Implemented in db1c71b; validated with rtk npm test (983 passed) and rtk npm run lint on 2026-08-22. Source: `db1c71b`
- request-AC2 -> This task. Proof: Implemented in db1c71b; validated with rtk npm test (983 passed) and rtk npm run lint on 2026-08-22. Source: `db1c71b`
- request-AC3 -> This task. Proof: Implemented in db1c71b; validated with rtk npm test (983 passed) and rtk npm run lint on 2026-08-22. Source: `db1c71b`
- request-AC4 -> This task. Proof: Implemented in db1c71b; validated with rtk npm test (983 passed) and rtk npm run lint on 2026-08-22. Source: `db1c71b`

# Validation
- (no validation recorded yet)
- rtk npm test passed on 2026-08-22: 983 passed in 19.06s
- rtk npm run lint passed on 2026-08-22: all checks passed
- Finish workflow executed on 2026-08-22.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-22.
- Linked backlog item(s): `item_138_drain_codex_app_server_diagnostic_stderr_safely`, `item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts`
- Related request(s): `req_069_harden_codex_probe_process_and_package_smoke_coverage`

# Links
- Request: `req_069_harden_codex_probe_process_and_package_smoke_coverage`
- Product brief(s): `prod_052_reliable_codex_diagnostics_in_packaged_installs`
- Architecture decision(s): (none yet)
