## item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions - Launch the correct Logics Fleet or project viewer from tray actions
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 10%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-13 00:53:55

# AI Context
- Summary: Make declared Logics actions detached browser launches, with Fleet for the global action and validated project context for a focused row.
- Keywords: launch, correct, logics, fleet, project, viewer, tray, actions
- Use when: Repairing the first-party Logics tray card action contract and launcher.
- Skip when: Managing a viewer server in CDX, embedding a browser, or adding plugin-defined commands.

# Problem
- Tray card actions currently block on a server command, omit the browser-open request, and discard the repository context needed by a focused Logics reference.
- The visible card can therefore describe a repository correctly while its action either appears inert or launches outside that repository.

# Scope
- In:
  - Use a detached CDX-owned viewer launcher for tray actions, with an explicit browser-open request and no tray-side server management.
  - Route Open Logics to the supported Fleet viewer entry point.
  - Extend the bounded first-party Logics card/action contract with validated originating repository context for focused rows only.
  - Launch focused rows in their originating repository, preserving the fixed action vocabulary and WSL environment resolution in CDX.
  - Add regression tests for argv, cwd, detachment, malformed context, global versus focused routing, and macOS menu dispatch.
- Out:
  - Starting, supervising, or duplicating a Logics server inside the Rust tray companion.
  - Embedding a web view, exposing a port in CDX, adding a plugin marketplace, or allowing plugin-defined shell commands.
  - Publishing repository paths into alert payloads or user-facing tray labels.

# Acceptance criteria
- AC1: Global Open Logics returns promptly and launches the supported Fleet viewer with an explicit browser-open request.
- AC2: A focused row returns promptly and launches the viewer with the row reference, browser-open request, and exact originating repository as cwd.
- AC3: The action context is schema-validated, bounded, first-party owned, and unavailable actions fail safely without executing a command.
- AC4: Existing plugin isolation, action-id validation, repository privacy, native/WSL resolution, and base tray behaviour remain intact.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC1: Global Open Logics returns promptly and launches the supported Fleet viewer with an explicit browser-open request.
- request-AC6 -> This backlog slice. Proof: AC2: A focused row returns promptly and launches the viewer with the row reference, browser-open request, and exact originating repository as cwd.
- request-AC7 -> This backlog slice. Proof: AC3: The action context is schema-validated, bounded, first-party owned, and unavailable actions fail safely without executing a command.
- request-AC8 -> This backlog slice. Proof: AC4: Existing plugin isolation, action-id validation, repository privacy, native/WSL resolution, and base tray behaviour remain intact.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_041_contextual_cdx_tray_recovery_paths`
- Architecture decision(s): (none yet)
- Request: `req_054_group_tray_alerts_by_session_and_make_logics_actions_reliably_open_the_viewer`
- Primary task(s): `task_065_orchestrate_grouped_tray_alerts_and_reliable_logics_viewer_actions`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
