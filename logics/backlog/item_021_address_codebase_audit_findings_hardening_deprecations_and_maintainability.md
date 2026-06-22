## item_021_address_codebase_audit_findings_hardening_deprecations_and_maintainability - Address codebase audit findings: hardening, deprecations, and maintainability
> From version: 0.9.7
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
A full codebase audit (2026-06-22) found no critical defects, but surfaced one privacy gap, two robustness issues (one a hard deprecation), and several maintainability/tooling gaps that should be addressed before the project leaves Alpha.
The changes must preserve current behavior and security posture (AES-256-GCM auth bundles, `0o600`/`0o700` permissions, atomic writes, path-traversal guards) while removing latent risks and reducing maintenance cost.

# Scope
- In:
  - one coherent delivery slice from the source request
- Out:
  - unrelated sibling slices that should stay in separate backlog items instead of widening this doc

# Acceptance criteria
- AC1: Encrypted bundles no longer expose session names in cleartext; `session_names` lives inside the encrypted payload (or is omitted from the wrapper), with round-trip export/import tests and backward-compatible decode of existing bundles.
- AC2: Tree removal no longer relies on the deprecated `rmtree(onerror=...)`; it uses `onexc` on Python >= 3.12 with an `onerror` fallback for 3.9-3.11, and runs warning-free.
- AC3: The bundle/crypto tests `skip` cleanly (with a clear reason) when `cryptography` is unavailable instead of failing.
- AC4: Command routing in `cli.py` uses an explicit dispatch table, and the per-command "suppress update notice" decision is data-driven (no inline hand-maintained command list).
- AC5: CI runs a real linter (e.g. `ruff check`) and the same test runner used locally (`pytest`) with coverage reported; a documented dev-dependency group installs the toolchain.
- AC6: A decision is recorded on the minimum supported Python version (keep 3.9 vs raise the floor), with `pyproject.toml` classifiers updated to match.
- AC7: No regression in security posture or existing CLI behavior; full suite green on supported interpreters.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Encrypted bundles no longer expose session names in cleartext; `session_names` lives inside the encrypted payload (or is omitted from the wrapper), with round-trip export/import tests and backward-compatible decode of existing bundles.
- request-AC2 -> This backlog slice. Proof: AC2: Tree removal no longer relies on the deprecated `rmtree(onerror=...)`; it uses `onexc` on Python >= 3.12 with an `onerror` fallback for 3.9-3.11, and runs warning-free.
- request-AC3 -> This backlog slice. Proof: AC3: The bundle/crypto tests `skip` cleanly (with a clear reason) when `cryptography` is unavailable instead of failing.
- request-AC4 -> This backlog slice. Proof: AC4: Command routing in `cli.py` uses an explicit dispatch table, and the per-command "suppress update notice" decision is data-driven (no inline hand-maintained command list).
- request-AC5 -> This backlog slice. Proof: AC5: CI runs a real linter (e.g. `ruff check`) and the same test runner used locally (`pytest`) with coverage reported; a documented dev-dependency group installs the toolchain.
- request-AC6 -> This backlog slice. Proof: AC6: A decision is recorded on the minimum supported Python version (keep 3.9 vs raise the floor), with `pyproject.toml` classifiers updated to match.
- request-AC7 -> This backlog slice. Proof: AC7: No regression in security posture or existing CLI behavior; full suite green on supported interpreters.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_009_address_codebase_audit_findings`
- Primary task(s): `task_020_address_codebase_audit_findings_hardening_deprecations_and_maintainability`

# AI Context
- Summary: Address codebase audit findings: hardening, deprecations, and maintainability
- Keywords: backlog-groom, request, address codebase audit findings: hardening, deprecations, and maintainability, bounded slice
- Use when: Use when implementing or reviewing the delivery slice for Address codebase audit findings: hardening, deprecations, and maintainability.
- Skip when: Skip when the change is unrelated to this delivery slice or its linked request.

# Priority
- Impact:
- Urgency:

# Notes
- Hybrid rationale: Derived from request `req_009_address_codebase_audit_findings` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_009_address_codebase_audit_findings.md`.
- Generated locally by logics-manager.

# Tasks
- `task_020_address_codebase_audit_findings_hardening_deprecations_and_maintainability`
