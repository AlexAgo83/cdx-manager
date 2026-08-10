## item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls - Add explicit CDX tray lifecycle, capacity, privacy, and recovery controls
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 70%
> Complexity: High
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

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

# Acceptance criteria
- AC1: cdx tray install never enables startup, cdx tray autostart on and off are explicit and idempotent and report the real platform state, and one tray instance owns a user session while a duplicate launch reports the existing one.
- AC2: One accessible, privacy-preserving capacity state names the most constrained usable source and its reset in the tooltip and menu, renders an explicit unknown state, and never relies on colour alone or exposes session, repository, task, or preview detail while closed.
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
