## req_069_harden_codex_probe_process_and_package_smoke_coverage - Harden Codex probe process and package smoke coverage
> From version: 0.20.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 11:59:10

# AI Context
- Summary: Prevent subprocess backpressure from impersonating an authentication failure and verify doctor from distributable artifacts.
- Keywords: harden, codex, probe, process, package, smoke, coverage
- Use when: Improving the reliability of Codex app-server diagnostics and package release checks.
- Skip when: Adding live provider integration tests, credentials, or release publication automation.

# Needs
- The Codex app-server diagnostic awaits stdout while stderr is piped but never consumed; provider diagnostics must not deadlock or time out merely because stderr is written.
- Published npm and wheel artifacts need to execute a non-destructive doctor smoke in CI, so a source-only validation cannot mask a packaging regression.

# Context
- `src/codex_usage.py` creates the app-server process with both stdout and stderr pipes, but starts a reader thread only for stdout before awaiting JSON-RPC responses.
- `.github/workflows/ci.yml` checks `cdx doctor --json` from a source install on one platform, while the packaged npm and wheel jobs only execute `--version` and `schema --json`.
- The work must stay local and deterministic: no live provider account, credential, network call, or release publication is required for CI smoke coverage.

# Acceptance criteria
- AC1: The app-server diagnostic cannot block because stderr fills while stdout is awaited; its existing timeout and token-safe error contract remain intact.
- AC2: Focused tests simulate stderr output alongside a valid JSON-RPC response and prove that the diagnostic completes.
- AC3: CI installs both packed npm and wheel artifacts and runs a controlled `cdx doctor --json` smoke using local provider shims.
- AC4: The smoke proves the packaged command can create isolated profiles and report doctor output without a real provider login or network request.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_052_reliable_codex_diagnostics_in_packaged_installs`
- Architecture decision(s): (none yet)

# References
- src/codex_usage.py
- test/test_codex_usage_py.py
- .github/workflows/ci.yml
- package.json
- pyproject.toml

# Backlog
- `item_138_drain_codex_app_server_diagnostic_stderr_safely`
- `item_139_smoke_test_doctor_from_packed_npm_and_wheel_artifacts`
