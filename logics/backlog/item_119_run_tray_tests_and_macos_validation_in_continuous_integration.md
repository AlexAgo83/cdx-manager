## item_119_run_tray_tests_and_macos_validation_in_continuous_integration - Run tray tests and macOS validation in continuous integration
> From version: 0.19.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Repository reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:01

# AI Context
- Summary: Put existing Rust tray tests and safe macOS validation on the pull-request path.
- Keywords: run, tray, tests, macos, validation, continuous, integration
- Use when: Changing CI or tray companion validation.
- Skip when: Automating signed release packaging.

# Problem
- The Rust tray has 96 local tests but CI does not execute cargo test or build the tray.
- macOS-specific tray, notification, and terminal code has no CI lane.

# Scope
- In:
  - Add cargo test for the tray to CI.
  - Add a bounded macOS lane that compiles/tests the tray and performs only safe platform-independent smoke checks.
  - Add targeted command-contract tests for currently uncovered tray paths.
- Out:
  - Automating interactive GUI permission dialogs.
  - Replacing the existing Python CI matrix.

# Acceptance criteria
- CI runs cargo test --manifest-path tray/Cargo.toml on every pull request.
- A macOS job validates the tray build and tests without requiring signing secrets.
- Focused tray command tests cover the added CI-facing behaviour.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: CI runs cargo test --manifest-path tray/Cargo.toml on every pull request.
- request-AC7 -> This backlog slice. Proof: A macOS job validates the tray build and tests without requiring signing secrets.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)
- Request: `req_061_harden_repository_reliability_release_verification_and_cli_contracts`
- Primary task(s): `task_071_orchestrate_repository_reliability_and_release_contract_hardening`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
