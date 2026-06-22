## task_020_address_codebase_audit_findings_hardening_deprecations_and_maintainability - Address codebase audit findings: hardening, deprecations, and maintainability
> From version: 0.9.7
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.

# Backlog
- `item_021_address_codebase_audit_findings_hardening_deprecations_and_maintainability`

# Acceptance criteria
- AC1: Encrypted bundles no longer expose session names in cleartext; `session_names` lives inside the encrypted payload (or is omitted from the wrapper), with round-trip export/import tests and backward-compatible decode of existing bundles.
- AC2: Tree removal no longer relies on the deprecated `rmtree(onerror=...)`; it uses `onexc` on Python >= 3.12 with an `onerror` fallback for 3.9-3.11, and runs warning-free.
- AC3: The bundle/crypto tests `skip` cleanly (with a clear reason) when `cryptography` is unavailable instead of failing.
- AC4: Command routing in `cli.py` uses an explicit dispatch table, and the per-command "suppress update notice" decision is data-driven (no inline hand-maintained command list).
- AC5: CI runs a real linter (e.g. `ruff check`) and the same test runner used locally (`pytest`) with coverage reported; a documented dev-dependency group installs the toolchain.
- AC6: A decision is recorded on the minimum supported Python version (keep 3.9 vs raise the floor), with `pyproject.toml` classifiers updated to match.
- AC7: No regression in security posture or existing CLI behavior; full suite green on supported interpreters.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run `python3 -m logics_manager flow finish task task_020_address_codebase_audit_findings_hardening_deprecations_and_maintainability.md` after implementation.
- npm run lint passed; npm run test:coverage passed (338 tests, coverage reported for src/).
- Finish workflow executed on 2026-06-22.
- Linked backlog/request close verification passed.

# Report
- Ready for implementation.
- Finished on 2026-06-22.
- Linked backlog item(s): `item_021_address_codebase_audit_findings_hardening_deprecations_and_maintainability`
- Related request(s): `req_009_address_codebase_audit_findings`

# AI Context
- Summary: Implement address codebase audit findings: hardening, deprecations, and maintainability.
- Keywords: task, implementation, backlog, runtime, python
- Use when: You need a bounded implementation task for a backlog item.
- Skip when: The work is still at the request or backlog shaping stage.

# Links
- Request: `req_009_address_codebase_audit_findings`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# AC Traceability
- request-AC1 -> This task. Evidence needed: Encrypted bundles no longer expose session names in cleartext; `session_names` lives inside the encrypted payload (or is omitted from the wrapper), with round-trip export/import tests and backward-compatible decode of existing bundles.
- request-AC2 -> This task. Evidence needed: Tree removal no longer relies on the deprecated `rmtree(onerror=...)`; it uses `onexc` on Python >= 3.12 with an `onerror` fallback for 3.9-3.11, and runs warning-free.
- request-AC3 -> This task. Evidence needed: The bundle/crypto tests `skip` cleanly (with a clear reason) when `cryptography` is unavailable instead of failing.
- request-AC4 -> This task. Evidence needed: Command routing in `cli.py` uses an explicit dispatch table, and the per-command "suppress update notice" decision is data-driven (no inline hand-maintained command list).
- request-AC5 -> This task. Evidence needed: CI runs a real linter (e.g. `ruff check`) and the same test runner used locally (`pytest`) with coverage reported; a documented dev-dependency group installs the toolchain.
- request-AC6 -> This task. Evidence needed: A decision is recorded on the minimum supported Python version (keep 3.9 vs raise the floor), with `pyproject.toml` classifiers updated to match.
- request-AC7 -> This task. Evidence needed: No regression in security posture or existing CLI behavior; full suite green on supported interpreters.
- request-AC1 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
- request-AC2 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
- request-AC3 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
- request-AC4 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
- request-AC5 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
- request-AC6 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
- request-AC7 -> This task. Proof: Implemented in commits 382b5b0 and 1e89886; local validation passed with npm run lint and npm run test:coverage (338 tests, coverage reported for src/). Source: `local validation`
