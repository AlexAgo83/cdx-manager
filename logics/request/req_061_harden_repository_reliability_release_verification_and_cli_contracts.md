## req_061_harden_repository_reliability_release_verification_and_cli_contracts - Harden repository reliability, release verification, and CLI contracts
> From version: 0.19.1
> Schema version: 1.0
> Status: Draft
> Understanding: 100%
> Confidence: 95%
> Complexity: High
> Theme: Repository reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:09:00

# AI Context
- Summary: Deliver six bounded reliability slices from the repository review without a platform or CLI rewrite.
- Keywords: harden, repository, reliability, release, verification, cli, contracts
- Use when: Planning CI, release, persistence, usage-accounting, or repository-hygiene hardening.
- Skip when: Implementing unrelated provider capabilities.

# Needs
- The repository review found release, persistence, and observability paths that are locally implemented but not fully verified or consistently bounded in CI and runtime behaviour.
- CDX must preserve its existing CLI and provider contracts while making tray delivery, release artifacts, detached-run recovery, and token accounting more resilient.
- The review also found test-coverage, module-boundary, contributor-documentation, and Logics-state gaps that weaken maintenance confidence.

# Context
- Local checks on 2026-08-13 passed: npm run test:coverage reported 82% total Python coverage, npm run lint passed, cargo test --manifest-path tray/Cargo.toml passed 96 tests, and npm audit --omit=dev reported zero production vulnerabilities.
- CI currently runs Python checks on Ubuntu and Windows, but it does not run the Rust tray test suite or a macOS tray lane. npm packaging is dry-run only before release and PyPI package construction occurs in the publication workflow.
- The session store performs fsync-backed atomic writes, while the detached-run registry does a temp-file rename without file or directory fsync and has unbounded POSIX lock acquisition.
- Interactive usage persists cached input tokens, but shared headless usage normalization and stats aggregation omit that optional field. Transcript discovery currently walks provider history and reads the selected file without an explicit I/O budget.
- The scope deliberately excludes a rewrite: existing domains and helper patterns should be extracted or reused only where they reduce a measured operational risk.

# Acceptance criteria
- AC1: CI runs the Rust tray test suite and a bounded macOS tray validation in addition to existing Python checks.
- AC2: npm and PyPI distributable artifacts are built, inspected, installed in clean environments, and smoke-tested before publication.
- AC3: Release workflows pin third-party actions to immutable revisions while retaining the minimum permissions required for release work.
- AC4: Detached-run registry writes and lock acquisition are crash-safe and bounded on POSIX and Windows, with regression tests.
- AC5: Headless and interactive usage share one documented schema that preserves optional cached input without changing provider total semantics.
- AC6: Interactive transcript discovery and parsing remain fail-open but have an explicit bounded I/O path and regression tests.
- AC7: Focused contract tests cover currently under-tested tray and context-memory operational branches.
- AC8: Provider runtime and CLI argument code are split only along verified existing seams, retaining public CLI behaviour and coverage.
- AC9: Contributor instructions and historical Logics progress state accurately describe the current validation and workflow contracts.

# AC Traceability
- request-AC1 -> This task. Proof: CI matrix covers macOS and runs `cargo test --manifest-path tray/Cargo.toml`; validated by the Rust suite (96 passed).
- request-AC2 -> This task. Proof: CI installs the packed npm archive and built wheel in clean environments, then runs `cdx schema --json`.
- request-AC3 -> This task. Proof: release workflow actions are pinned to immutable revisions and inspected by CI configuration review.
- request-AC4 -> This task. Proof: `61f8ae8` and `9cd9fa2` add durable writes, bounded POSIX locks, and regression tests.
- request-AC5 -> This task. Proof: `f10096f` and `9cd9fa2` normalize cached input tokens without double-counting; 898 Python tests pass.
- request-AC6 -> This task. Proof: interactive transcript discovery has byte, candidate, and elapsed-time bounds with regression tests.
- request-AC7 -> This task. Proof: `96198c4` adds CLI context/memory lifecycle tests, raising targeted coverage from 42% to 66%.
- request-AC8 -> This task. Proof: existing command-family seams remain intact; focused contract tests preserve public CLI behavior without a generic framework.
- request-AC9 -> This task. Proof: `dfa2816` restores contributor guidance and historical workflow indicators; Logics lint/audit pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_047_reliable_delivery_and_runtime_contracts`
- Architecture decision(s): (none yet)

# References
- .github/workflows/ci.yml
- .github/workflows/build-tray-assets.yml
- .github/workflows/publish-npm.yml
- .github/workflows/publish-pypi.yml
- CONTRIBUTING.md
- README.md
- src/interactive_usage.py
- src/run_usage.py
- src/commands/status.py
- src/run_registry.py
- src/session_store.py
- src/provider_runtime.py
- src/cli_args.py

# Backlog
- `item_119_run_tray_tests_and_macos_validation_in_continuous_integration`
- `item_120_verify_installable_package_artifacts_before_release`
- `item_121_make_detached_run_registry_persistence_durable_and_bounded`
- `item_122_unify_and_bound_interactive_token_usage_accounting`
- `item_123_cover_operational_command_boundaries_and_extract_measured_seams`
- `item_124_restore_contributor_and_logics_workflow_signal_accuracy`
