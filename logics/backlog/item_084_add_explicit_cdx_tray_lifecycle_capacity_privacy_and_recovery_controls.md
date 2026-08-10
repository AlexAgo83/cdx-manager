## item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls - Add explicit CDX tray lifecycle, capacity, privacy, and recovery controls
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 92%
> Progress: 95%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 22:49:36

# AI Context
- Summary: Add explicit CDX tray lifecycle, capacity, privacy, and recovery controls
- Keywords: scaffolded-backlog, add explicit cdx tray lifecycle, capacity, privacy, and recovery controls, implementation-ready
- Use when: Implementing the scaffolded slice for Add explicit CDX tray lifecycle, capacity, privacy, and recovery controls.
- Skip when: The change belongs to another backlog slice.

# Problem
- A desktop utility that starts unexpectedly, duplicates its icon, obscures failure, or leaks details loses trust even if its usage data is correct.

# Scope
- In:
  - Implement explicit autostart, single-instance, doctor, staged update recovery, and honest installed-state reporting.
  - Map one least-available usable quota state to accessible icon, tooltip, and menu text while preserving notification and privacy boundaries.
  - Add focused automated checks and managed-macOS smoke validation.
- Out:
  - Background self-update, automatic tray activation, cross-machine monitoring, quota alerts, and rewriting the dependent alert or plugin contracts.

# Delivery record
- AC1 is met: `install` never enables startup, `autostart on|off` are explicit, idempotent and read back from the platform rather than from a recorded intention, and a second companion exits 3 naming the pid that holds the lock. Verified on macOS and on Windows.
- AC2 is met: the tooltip names the most constrained capacity, its figure, its freshness and its reset in words rather than by shape, and never the session name, which stays one click away in the menu. Composed in CDX so no backend can say more than the rule allows.
- AC4 is met: an update verifies, stages, proves the replacement starts, and only then retires the previous companion; a failed probe leaves the working one installed and `doctor` names the interrupted state.
- AC5 now includes the two capabilities that decide whether the companion's output ever reaches a person, and both fail *silently* on the platform that gates them — the only reason they earn a diagnostic line at all. Windows shows a toast from a non-packaged program only when a Start Menu shortcut carrying its AppUserModelID exists; without one the notification API succeeds and nothing appears. Linux draws an icon only where something owns `org.kde.StatusNotifierWatcher`.
- Both verified on kdesktop rather than mocked. Windows reports `missing: C:\Users\aagos\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\CDX.lnk`, and that directory is real — it holds other applications' shortcuts, so the diagnostic points somewhere that exists. Ubuntu WSL reports `no org.kde.StatusNotifierWatcher: this desktop has no system tray`, the same words the Rust backend uses, because a diagnostic that disagreed with the thing it diagnoses would be worse than none.
- A failed probe reports `unknown`, not "no tray". Reporting absence would be a claim the probe never made, and would send someone installing an extension they may already have.
- That gap is now closed: `cdx tray install` creates the shortcut on Windows, carrying the `com.cdx.tray` AppUserModelID. Verified on kdesktop with native Python — the shortcut is written to the Start Menu, targets the real companion executable, and reads its identifier back.
- The identifier is the hard part and cannot be set through `WScript.Shell`: it lives in the shortcut's property store, reachable only through `IShellLink` plus `IPropertyStore`. One detail cost the first two attempts and is worth keeping: `PROPVARIANT` is 24 bytes on x64, and declaring it shorter lets `GetValue` write past the managed struct — the symptom is not a crash but a value that silently reads back as `VT_EMPTY`. Exactly the class of failure this whole slice is about.
- `create` reports success only when the identifier reads back. A `.lnk` that exists without one is a shortcut Windows will not route a toast through, so calling it created would reproduce the silent failure it exists to end.
- Failing to write the shortcut never fails the install. The companion runs either way; only its toasts would go nowhere, and doctor says so. Three tests cover the refusal paths.
- The shortcut is recorded in the install state only when CDX created it, so `uninstall` removes it and AC3 still holds: nothing CDX did not write ends up on the removal list.

# Acceptance criteria
- AC1: cdx tray install never enables startup, cdx tray autostart on and off are explicit and idempotent and report the real platform state, and one tray instance owns a user session while a duplicate launch reports the existing one.
- AC2: One accessible, privacy-preserving capacity state names the most constrained usable capacity, its remaining figure and its reset in the tooltip, in words rather than by shape, and without the session name; the menu carries the name. renders an explicit unknown state, and never relies on colour alone or exposes session, repository, task, or preview detail while closed.
- AC3: Completion and attention alerts respect native notification settings and Do Not Disturb, use no urgent interruption mode, and quota urgency produces an icon state rather than a new toast category.
- AC4: A cdx-managed update verifies the matching asset, stages it, starts the replacement, and only then retires the previous companion; a failed replacement leaves the prior working version running and cdx tray doctor explains the partial state and its recovery.
- AC5: cdx tray doctor reports instance ownership, startup state, snapshot freshness, installed version, and desktop capability as bounded diagnostics without a persistent background service, and on Windows it checks the Start Menu shortcut that toasts depend on, because a missing shortcut drops notifications silently.
- AC6: The managed macOS smoke run verifies that the notification authorization granted to the signed companion survives a companion update, and records the observed behaviour whether it holds or not.
- AC7: Automated checks and managed macOS smoke validation pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: cdx tray install never enables startup, and cdx tray autostart on and off are explicit, idempotent, and report the real platform state.
- request-AC2 -> This backlog slice. Proof: AC1: One tray instance owns a user session and a duplicate launch reports the existing one. AC5: cdx tray doctor reports instance ownership, startup state, snapshot freshness, installed version, and desktop capability without a persistent background service.
- request-AC4 -> This backlog slice. Proof: AC2: One accessible, privacy-preserving capacity state names the most constrained usable source and its reset, renders an explicit unknown state, and never relies on colour alone.
- request-AC5 -> This backlog slice. Proof: AC3: Alerts respect native notification settings and Do Not Disturb, and quota urgency produces an icon state rather than a new toast category. AC2: No tray surface exposes session, repository, task, or preview detail while closed.
- request-AC6 -> This backlog slice. Proof: AC4: A cdx-managed update stages a verified replacement, starts it, then retires the previous companion, and a failure leaves the prior working version running with a doctor-explained recovery.
- request-AC8 -> This backlog slice. Proof: AC6: The managed macOS smoke run verifies that the notification authorization survives a companion update. AC7: Automated checks and managed macOS smoke validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Settled in `adr_005_cdx_tray_runtime_and_companion_transport_boundary`

# Links
- Product brief(s): `prod_027_trustworthy_cdx_tray_operation`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
- Request: `req_038_harden_cdx_tray_lifecycle_clarity_and_platform_validation`
- Primary task(s): `task_049_orchestrate_trustworthy_cdx_tray_operation_and_platform_validation`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
