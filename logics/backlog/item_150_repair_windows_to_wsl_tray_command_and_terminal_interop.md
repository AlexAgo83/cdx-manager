## item_150_repair_windows_to_wsl_tray_command_and_terminal_interop - Repair Windows-to-WSL tray command and terminal interop
> From version: 0.20.9
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 75%
> Complexity: Medium
> Theme: Platform support
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:39:34

# AI Context
- Summary: Implements the Windows-to-WSL tray interop slice for req_073 findings 10-12: argv-safe config actions, Windows-launchable terminal candidates, and cmd-compatible WSL command launch.
- Keywords: req_073, tray win.rs, Transport::Wsl, cdx config, terminal_candidates, cmd.exe, wt.exe, PowerShell, Ubuntu WSL
- Use when: Changing Windows tray actions that call CDX through WSL or terminal preference handling consumed by the Windows companion.
- Skip when: The work is about credential import, memory append locking, detached provider lifecycle, or tray update staging.

# Problem
- The Windows tray can send multi-word CDX actions as one argument, offer Linux-only terminal choices from WSL, and run cmd preferences with PowerShell flags.

# Scope
- In:
  - Represent tray-launched CDX commands as argv parts rather than single shell-like strings where WSL interop needs multiple arguments.
  - Ensure a Windows tray using WSL exposes only Windows-launchable terminal preferences and falls back from unsupported stored values.
  - Run cmd preferences through a verified cmd command form for WSL actions.
  - Add Rust command-construction tests and Tower native Windows plus Ubuntu WSL smoke checks.
- Out:
  - No support for arbitrary terminal commands, WSL GUI terminal discovery, multiple WSL distributions, or Linux desktop expansion.

# Acceptance criteria
- AC1: Session config clicks execute cdx config <session> in the configured WSL distribution.
- AC2: Windows-to-WSL snapshots present only launchable Windows terminal options or a working default.
- AC3: cmd preference launches the selected WSL-backed CDX action instead of opening an idle shell.

# AC Traceability
- request-AC10 -> This backlog slice. Proof: AC1: Session config clicks execute cdx config <session> in the configured WSL distribution.
- request-AC11 -> This backlog slice. Proof: AC2: Windows-to-WSL snapshots present only launchable Windows terminal options or a working default.
- request-AC12 -> This backlog slice. Proof: AC3: cmd preference launches the selected WSL-backed CDX action instead of opening an idle shell.
- request-AC13 -> This backlog slice. Proof: AC3: cmd preference launches the selected WSL-backed CDX action instead of opening an idle shell.
> Shared proof: request-AC12 and request-AC13 share the same final validation wave for this slice.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Primary task(s): `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
