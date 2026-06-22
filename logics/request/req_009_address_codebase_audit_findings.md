## req_009_address_codebase_audit_findings - Address codebase audit findings: hardening, deprecations, and maintainability
> From version: 0.9.7
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- A full codebase audit (2026-06-22) found no critical defects, but surfaced one privacy gap, two robustness issues (one a hard deprecation), and several maintainability/tooling gaps that should be addressed before the project leaves Alpha.
- The changes must preserve current behavior and security posture (AES-256-GCM auth bundles, `0o600`/`0o700` permissions, atomic writes, path-traversal guards) while removing latent risks and reducing maintenance cost.

# Context
- Audit scope: `src/` (~10,336 LOC, Python 3.9-3.13) and `test/` (~8,472 LOC). Static review plus local `pytest`.
- Strong baseline confirmed: no `shell=True`, no bare `except`, no `eval`/`exec`/`pickle`, no mutable default args, versions consistent across `VERSION`/`package.json`/`pyproject.toml`, encryption and credential handling are sound.
- Findings (by severity):
  - **S1 — privacy (low):** in encrypted bundles, `session_names` is stored in cleartext in the wrapper (`src/backup_bundle.py:108`), leaking account names without the passphrase.
  - **B1 — deprecation (medium):** `shutil.rmtree(..., onerror=...)` (`src/fs_utils.py:50`) is deprecated since Python 3.12 and **removed in 3.14**; emits `DeprecationWarning` on supported interpreters.
  - **B2 — test fragility (low):** 6 tests fail (not skip) when `cryptography` is absent from the running interpreter; CI passes only because it `pip install -e .`. A fresh `pytest` clone shows false failures.
  - **M1 — monolith (medium):** `src/cli_commands.py` is 3,073 lines / 35 handlers in one file.
  - **M2 — fragile dispatch (medium):** `src/cli.py` routes 35 commands via a long `if command == ...` chain, and `cli.py:289-291` maintains an inline negative list of command names for `update_notices` that must be hand-edited per new command (silent-bug risk).
  - **M3 — no typing/linter (low):** no type hints; CI lint step is only `py_compile`.
  - **T1 — CI/coverage drift (low):** CI runs `unittest discover`, not `pytest`; coverage is not measured in CI despite a local `.coverage`.
  - **T2 — tooling (low):** no `ruff`/`flake8`/`mypy` and no dev-dependency group declared.
  - **T3 — runtime floor (low):** `requires-python = ">=3.9"`; Python 3.9 is EOL (Oct 2025).

# Acceptance criteria
- AC1: Encrypted bundles no longer expose session names in cleartext; `session_names` lives inside the encrypted payload (or is omitted from the wrapper), with round-trip export/import tests and backward-compatible decode of existing bundles.
- AC2: Tree removal no longer relies on the deprecated `rmtree(onerror=...)`; it uses `onexc` on Python >= 3.12 with an `onerror` fallback for 3.9-3.11, and runs warning-free.
- AC3: The bundle/crypto tests `skip` cleanly (with a clear reason) when `cryptography` is unavailable instead of failing.
- AC4: Command routing in `cli.py` uses an explicit dispatch table, and the per-command "suppress update notice" decision is data-driven (no inline hand-maintained command list).
- AC5: CI runs a real linter (e.g. `ruff check`) and the same test runner used locally (`pytest`) with coverage reported; a documented dev-dependency group installs the toolchain.
- AC6: A decision is recorded on the minimum supported Python version (keep 3.9 vs raise the floor), with `pyproject.toml` classifiers updated to match.
- AC7: No regression in security posture or existing CLI behavior; full suite green on supported interpreters.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Scope
- In: S1 (bundle metadata), B1 (`onexc`), B2 (test skips), M2 (dispatch table + data-driven notices), T1/T2 (CI linter + pytest/coverage + dev deps), T3 (Python floor decision).
- Out (defer to follow-up backlog slices): M1 full split of `cli_commands.py` and M3 broad type-hinting rollout — large refactors better sequenced after the quick wins land.

# Risks
- Moving `session_names` into the encrypted payload can break tooling that reads the wrapper; mitigate with schema/version handling and backward-compatible decode.
- Reworking command dispatch touches every command path; mitigate with the existing CLI test coverage and incremental migration.
- Raising the Python floor would drop 3.9 users; treat as an explicit, reversible decision (AC6) rather than an implicit side effect.

# Companion docs
- Product brief(s): (none needed; internal quality work)
- Architecture decision(s): (consider an ADR for AC4 dispatch model and AC6 Python floor if the change is non-trivial)

# References
- `src/backup_bundle.py:108`
- `src/fs_utils.py:50`
- `src/cli.py:289`
- `src/cli_commands.py`
- `.github/workflows/ci.yml`
- `pyproject.toml`

# AI Context
- Summary: Bounded quality/hardening request derived from the 2026-06-22 audit; fixes one privacy gap, a 3.14-breaking deprecation, fragile tests, and CI/dispatch maintainability, while deferring the large `cli_commands.py` split and type-hint rollout.
- Keywords: audit, hardening, deprecation, rmtree-onexc, bundle-encryption, cli-dispatch, ci-linting, python-floor
- Use when: planning the cleanup work that follows the audit.
- Skip when: scoping the large structural refactor of `cli_commands.py` (track that as its own slice).

# Backlog
- none
- `item_021_address_codebase_audit_findings_hardening_deprecations_and_maintainability`
