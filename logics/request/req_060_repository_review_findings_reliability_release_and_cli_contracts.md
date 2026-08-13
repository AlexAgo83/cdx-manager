## req_060_repository_review_findings_reliability_release_and_cli_contracts - Repository review findings: reliability, release, and CLI contracts
> From version: 0.19.1
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Repository health
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 22:05:20

# AI Context
- Summary: Evidence-backed candidates from a repository-wide review; capture only, with no implementation commitment.
- Keywords: repository, review, CI, release, persistence, tokens, tray, CLI, tests, security
- Use when: Prioritising post-review reliability, delivery, and maintainability work.
- Skip when: Implementing an already-scoped request.

# Needs
- P1 — Exercise the Rust tray in CI. `.github/workflows/ci.yml` only runs Python lint/tests on Ubuntu and Windows; it never runs `cargo test --manifest-path tray/Cargo.toml` (96 local tests passed) or builds the tray.
- P1 — Add a macOS CI lane for the tray and terminal integration. The tray has macOS-specific code in `tray/src/mac.rs`, `tray/src/mac_menu_open.rs`, and `tray/src/notify.rs`, but CI's matrix excludes macOS.
- P1 — Verify distributable artifacts before release. CI only does `npm pack --dry-run`; the PyPI wheel is built only after a release is published in `.github/workflows/publish-pypi.yml`. Build, inspect, install into a clean environment, and smoke the npm tarball and wheel before release publication.
- P1 — Pin GitHub Actions by immutable commit SHA and use a dependency-update mechanism. Release workflows grant `contents: write` while using mutable action tags such as `actions/checkout@v5` and `actions/download-artifact@v4`.
- P1 — Make the run-registry write as durable as the session store. `src/run_registry.py:91-103` does a temp-file rename without file or directory `fsync`; `src/session_store.py:35-63` already implements both. A power loss can therefore lose or truncate detached-run state despite the registry being the recovery source.
- P1 — Bound POSIX run-registry lock waits. `src/run_registry.py:57-75` has a 120-second bounded retry only on Windows; POSIX calls blocking `fcntl.flock` indefinitely, so a stuck lock holder can hang status/report commands forever.
- P1 — Unify the usage schema and expose cached input tokens. Interactive captures persist `cached_input_tokens` in `src/interactive_usage.py:74-80`, but `src/run_usage.py:3` and `src/commands/status.py:271-278` omit it, so `cdx stats --json` silently drops a collected metric.
- P1 — Bound interactive transcript discovery and parsing. `src/interactive_usage.py:23-41` walks every provider JSONL and then reads the newest file fully on each interactive exit. Large histories can turn a best-effort accounting feature into a noticeable exit delay; record or identify the expected transcript and impose a safe I/O budget.
- P2 — Raise coverage around operational command boundaries. The measured suite passed at 82% total coverage, but `src/commands/tray.py` and `src/commands/context_memory.py` are each 43%; both contain platform/process or persistent-user-content paths. Add focused contract tests for their untested branches before further feature work.
- P2 — Split the highest-coupling modules along existing domains. `src/provider_runtime.py` is 1,477 lines and `src/cli_args.py` is 1,016 lines; both centralise many unrelated provider/argument branches, making independent changes costly. Extract only the already-identifiable provider/auth/launch and command-family seams, with no new framework.
- P2 — Repair workflow data hygiene. `logics-manager health --format json` reported 17 health issues, including ten Done backlog items still at 90% or 95% progress (`item_041` through `item_050` in the report). Align historical status/progress so health can serve as a reliable release signal.
- P3 — Refresh contributor guidance. `CONTRIBUTING.md` tells contributors to update `test/test_cli_py.py`, which does not exist; current tests are command-module specific. Point contributors to the active test layout and the required Rust tray check.

# Context
- Review commands passed locally on 2026-08-13: `npm run test:coverage` (82% total Python coverage), `npm run lint`, `cargo test --manifest-path tray/Cargo.toml` (96 passed), and `npm audit --omit=dev --json` (0 vulnerabilities).
- This request intentionally does not claim a dependency vulnerability or a failing test. The candidates above are ranked by observed contract/recovery/coverage impact, not stylistic preference.
- In scope: correctness, resilience, delivery verification, test coverage, documentation, and workflow hygiene found in this review.
- Out of scope: implementation, new provider features, a rewrite of the CLI, and duplicating previously-open product work.

# Acceptance criteria
- AC1: CI runs Python checks, Rust tray tests, and an appropriate macOS tray lane before release publication.
- AC2: npm and PyPI artifacts are built, inspected, installed in clean environments, and smoke-tested before publication.
- AC3: Release workflows reduce mutable-action supply-chain exposure without weakening required permissions.
- AC4: Registry persistence and lock behaviour have bounded, crash-safe semantics on both POSIX and Windows, with tests.
- AC5: Usage accounting has one documented schema including optional cached input, and interactive transcript reading has a bounded failure-safe I/O path.
- AC6: The highest-risk untested command paths, contributor instructions, and historical Logics progress inconsistencies are corrected and validated.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `.github/workflows/ci.yml`
- `.github/workflows/build-tray-assets.yml`
- `.github/workflows/publish-npm.yml`
- `.github/workflows/publish-pypi.yml`
- `README.md`
- `CONTRIBUTING.md`
- `src/interactive_usage.py`
- `src/run_usage.py`
- `src/commands/status.py`
- `src/run_registry.py`
- `src/session_store.py`
- `src/provider_runtime.py`
- `src/cli_args.py`

# Backlog
- none
