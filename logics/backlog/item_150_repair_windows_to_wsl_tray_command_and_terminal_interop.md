## item_150_repair_windows_to_wsl_tray_command_and_terminal_interop - Repair Windows-to-WSL tray command and terminal interop
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Platform support
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:59:28

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
- request-AC10 -> This backlog slice. Proof: `tray/src/winterm.rs::tests::a_multi_argument_action_crosses_to_wsl_as_separate_arguments` and `::windows_terminal_keeps_the_cdx_arguments_separate_across_wsl`, confirmed on Tower Ubuntu WSL: `wsl.exe -d Ubuntu -- <cdx> config main` prints the launch settings while the old single-argument form answers `Unknown session: config main`.
- request-AC11 -> This backlog slice. Proof: `tray/src/winterm.rs::tests::a_wsl_produced_candidate_list_is_replaced_by_what_windows_can_open`, `::a_supported_stored_preference_survives_the_restriction` and `::only_terminals_present_on_this_host_are_offered`, against the real Tower reading: WSL advertises `['x-terminal-emulator']`, the Windows host has wt/powershell/cmd and no pwsh.
- request-AC12 -> This backlog slice. Proof: `tray/src/winterm.rs::tests::a_cmd_preference_runs_the_command_instead_of_opening_an_idle_shell`, confirmed on Tower Windows: `cmd.exe /k "wsl.exe -d Ubuntu -- <cdx> config main"` runs the command; `cmd.exe -NoExit -Command ...` fails with `'dx' is not recognized`.
- request-AC13 -> This backlog slice. Proof: `python3 -m pytest -q` (1,023 passed), `npm run lint` (all checks passed), `cargo test --manifest-path tray/Cargo.toml` (104 passed), `cargo check --target x86_64-pc-windows-msvc` (the Windows-only loop compiles), and the scoped Tower Windows plus Ubuntu WSL checks above.
> Shared proof: request-AC12 and request-AC13 share the same final validation wave for this slice.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Implementation
- `tray/src/winterm.rs` (new): the Windows command construction, deliberately not gated to Windows so `cargo test` covers the argv shapes on any host — argv parts across a WSL crossing, `cmd /k` for a cmd preference, the closed set of terminals a Windows companion can launch, and the fallback for a stored preference it cannot.
- `tray/src/win.rs`: tray actions pass argv parts rather than one shell-like string, spawning is all that is left here, and an unsupported preference opens the default console instead of logging and doing nothing.
- `tray/src/snapshot.rs`: on Windows the snapshot's terminal choices are restricted to what this companion can launch, because CDX serialises them from the host that answered the poll.

# Links
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Primary task(s): `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Notes
- Task `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop` was finished via `logics-manager flow finish task` on 2026-09-07.
