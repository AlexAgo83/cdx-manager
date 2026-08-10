## item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts - Constrain WSL and Linux tray support and validate it on real hosts
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 15%
> Complexity: Medium
> Theme: Platform support
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-10 21:26:47

# AI Context
- Summary: Constrain WSL and Linux tray support and validate it on real hosts
- Keywords: scaffolded-backlog, constrain wsl and linux tray support and validate it on real hosts, implementation-ready
- Use when: Implementing the scaffolded slice for Constrain WSL and Linux tray support and validate it on real hosts.
- Skip when: The change belongs to another backlog slice.

# Problem
- WSL and Linux tray assumptions vary by distribution and desktop environment, so broad claims without a configuration path and hardware smoke tests are unreliable.
- First hardware figures, from kdesktop: the bare wsl.exe crossing costs 132 ms, a full cdx tick 344 ms, and the companion's own end-to-end tick 285-320 ms, all warm. Recorded in adr_005; the remaining unknown is the cold-start cost when the distribution has been idle.

# Scope
- In:
  - Implement default and explicitly selected WSL distribution resolution with truthful diagnostics.
  - Detect Linux tray capability at runtime by resolving the org.kde.StatusNotifierWatcher D-Bus name, define the unsupported behaviour, and record the desktops actually verified rather than inferring support from a distribution name.
  - Run documented smoke checks on managed Windows plus Ubuntu WSL and record the results.
- Out:
  - Multiple-distribution aggregation, WSL GUI, network relays, universal Linux support, or production changes to managed hosts.

# Acceptance criteria
- AC1: Default and configured WSL distribution selection are deterministic and diagnose bad configuration.
- AC2: Linux tray capability is resolved at runtime through the StatusNotifierItem watcher, an absent watcher is reported safely, and the verified desktops are documented as tested rather than as supported by name.
- AC3: The managed Windows plus Ubuntu WSL smoke run measures the observed alert latency and the wsl.exe poll cost, confirms the tray stops polling when no session is enabled, verifies that a toast reaches Action Center through the installed Start Menu shortcut, and records whether the fetched asset carries a Zone.Identifier stream.
- AC4: Automated checks and the managed Windows plus Ubuntu WSL smoke validation pass.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: Default and configured WSL distribution selection are deterministic and diagnose bad configuration.
- request-AC7 -> This backlog slice. Proof: AC2: Linux tray capability is resolved at runtime through the StatusNotifierItem watcher, an absent watcher is reported safely, and the verified desktops are documented as tested.
- request-AC8 -> This backlog slice. Proof: AC3: The managed smoke run measures observed alert latency and wsl.exe poll cost. AC4: Automated checks and the managed Windows plus Ubuntu WSL smoke validation pass.

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
