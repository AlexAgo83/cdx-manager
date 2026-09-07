## item_149_make_tray_installation_and_probes_recoverable - Make tray installation and probes recoverable
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:39:34

# AI Context
- Summary: Implements the tray install recovery slice for req_073 findings 7-9: failed promotion rollback, Windows shortcut retargeting and ownership, and real macOS staged companion probing.
- Keywords: req_073, tray_install, tray_shortcut, companion.previous, companion.staged, Windows lnk, macOS open, staged probe
- Use when: Changing cdx tray install, update, shortcut, restart, or staged probe behavior.
- Skip when: The work is about credential import, backup decoding, run lifecycle, memory append locking, or WSL tray terminal actions.

# Problem
- Tray promotion, shortcut recording, and macOS staged probing can report success while leaving a missing executable, stale Windows shortcut, or untested app bundle.

# Scope
- In:
  - Restore the previous installed companion and restart it when staged promotion fails after retirement.
  - Keep Windows shortcut targets and uninstall ownership aligned with the final installed executable after successful or failed updates.
  - Make macOS staged probes execute the companion diagnostic path and reject launch failures.
  - Add temporary-archive tests and native platform smoke checks where required.
- Out:
  - No automatic update daemon, no tray UI redesign, and no admin-level installer changes.

# Acceptance criteria
- AC1: Promotion failure leaves the installed executable path valid and restarts a previously running companion.
- AC2: Windows shortcut TargetPath and owned paths reference the final live executable across update and uninstall flows.
- AC3: macOS staged probe fails for an unusable bundle and succeeds only for a real companion diagnostic invocation.

# AC Traceability
- request-AC7 -> This backlog slice. Proof: `test/test_tray_capability_py.py::test_a_promotion_failure_keeps_a_valid_installed_path_and_restarts_the_tray` — the recorded executable still exists after an injected rename failure, and the previously running companion is restarted on it.
- request-AC8 -> This backlog slice. Proof: `test/test_tray_capability_py.py::test_an_update_points_the_shortcut_at_the_live_executable_and_keeps_owning_it` — the shortcut is written once, against the promoted path, and `uninstall` removes it.
- request-AC9 -> This backlog slice. Proof: `test/test_tray_capability_py.py::test_the_staged_probe_runs_the_companion_and_refuses_an_unusable_bundle` — the probe invokes the bundle's own binary with `--print`, refuses a bundle with no runnable binary, and treats exec failures and signal deaths as launch failures while a non-zero diagnostic still passes.
- request-AC13 -> This backlog slice. Proof: `python3 -m pytest -q` (1,023 passed) and `npm run lint` (all checks passed). Rust tray tests and native Windows/WSL checks are carried by item_150, the slice that changes `tray/src/`.
> Shared proof: request-AC9 and request-AC13 share the same final validation wave for this slice.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Implementation
- `src/tray_install.py`: the staged-to-live promotion is guarded and restores the retired companion, reporting a `TrayInstallError` so the caller's restart path runs; `install(record=False)` no longer writes a Start Menu shortcut and the promotion writes one against the final executable, keeping it in the record's owned paths; `probe_command` resolves the binary inside a macOS app bundle and `_probe` reads its exit status.
- `align_companion` passes `env` through to the update and no longer lets a raw `OSError` skip its restart path.

# Links
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Primary task(s): `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
