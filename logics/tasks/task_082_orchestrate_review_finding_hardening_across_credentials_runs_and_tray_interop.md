## task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop - Orchestrate review finding hardening across credentials, runs, and tray interop
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:59:27
> Owner: claude-code

# AI Context
- Summary: Orchestration task for implementing four linked slices that close all req_074 acceptance criteria derived from req_073 review findings.
- Keywords: req_074, item_147, item_148, item_149, item_150, orchestration, ADR 009, Tower WSL validation
- Use when: Coordinating implementation order, evidence, and closeout for the review-finding hardening corpus.
- Skip when: Implementing an unrelated request or a single slice without touching orchestration evidence.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Start with credential and backup fixes because they protect authentication and restore paths.
- [x] 2. Then repair memory appends and headless run lifecycle so accepted work and child processes stay owned by CDX.
- [x] 3. Then repair tray installation, shortcut, and macOS probe recovery without changing tray feature scope.
- [x] 4. Finish with Windows-to-WSL tray argv and terminal interop, including Tower smoke checks.
- [x] 5. For each slice, add the smallest focused regressions, run targeted tests first, then Python/Rust suites, lint, Logics validation, and scoped Tower verification before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_147_preserve_credentials_and_portable_encrypted_backups`
- `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`
- `item_149_make_tray_installation_and_probes_recoverable`
- `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof: `test/test_profile_data_safety_py.py::test_merge_into_a_keychain_only_profile_keeps_the_local_account` — wave 1.
- request-AC1 -> This task. Proof: `test/test_profile_data_safety_py.py::test_merge_into_a_keychain_only_profile_keeps_the_local_account` — wave 1.
- request-AC2 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof: `test/test_profile_data_safety_py.py::test_late_force_import_failure_restores_the_original_credential` and `::test_force_import_reports_a_credential_it_could_not_restore` — wave 1.
- request-AC2 -> This task. Proof: `test/test_profile_data_safety_py.py::test_late_force_import_failure_restores_the_original_credential` and `::test_force_import_reports_a_credential_it_could_not_restore` — wave 1.
- request-AC3 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof: `test/test_session_service_py.py::test_encrypted_bundles_decode_with_the_kdf_their_exporter_recorded` — wave 1.
- request-AC3 -> This task. Proof: `test/test_session_service_py.py::test_encrypted_bundles_decode_with_the_kdf_their_exporter_recorded` — wave 1.
- request-AC4 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof: `test/test_context_store_py.py::test_concurrent_appends_keep_every_accepted_note` — wave 2.
- request-AC4 -> This task. Proof: `test/test_context_store_py.py::test_concurrent_appends_keep_every_accepted_note` — wave 2.
- request-AC5 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof: `test/test_commands_runs_py.py::test_detached_child_runs_the_cli_module_and_records_a_terminal_result` and `::test_detached_child_command_names_the_top_level_cli_module` — wave 2.
- request-AC5 -> This task. Proof: `test/test_commands_runs_py.py::test_detached_child_runs_the_cli_module_and_records_a_terminal_result` and `::test_detached_child_command_names_the_top_level_cli_module` — wave 2.
- request-AC6 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof: `test/test_commands_runs_py.py::test_interrupting_a_headless_run_kills_the_provider_and_records_cancellation` — wave 2.
- request-AC6 -> This task. Proof: `test/test_commands_runs_py.py::test_interrupting_a_headless_run_kills_the_provider_and_records_cancellation` — wave 2.
- request-AC7 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof: `test/test_tray_capability_py.py::test_a_promotion_failure_keeps_a_valid_installed_path_and_restarts_the_tray` — wave 3.
- request-AC7 -> This task. Proof: `test/test_tray_capability_py.py::test_a_promotion_failure_keeps_a_valid_installed_path_and_restarts_the_tray` — wave 3.
- request-AC8 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof: `test/test_tray_capability_py.py::test_an_update_points_the_shortcut_at_the_live_executable_and_keeps_owning_it` — wave 3.
- request-AC8 -> This task. Proof: `test/test_tray_capability_py.py::test_an_update_points_the_shortcut_at_the_live_executable_and_keeps_owning_it` — wave 3.
- request-AC9 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof: `test/test_tray_capability_py.py::test_the_staged_probe_runs_the_companion_and_refuses_an_unusable_bundle` — wave 3.
- request-AC9 -> This task. Proof: `test/test_tray_capability_py.py::test_the_staged_probe_runs_the_companion_and_refuses_an_unusable_bundle` — wave 3.
- request-AC10 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof: `tray/src/winterm.rs::tests::a_multi_argument_action_crosses_to_wsl_as_separate_arguments`, plus Tower Ubuntu WSL: `wsl.exe -d Ubuntu -- <cdx> config main` prints the settings, the old single-argument form does not — wave 4.
- request-AC10 -> This task. Proof: `tray/src/winterm.rs::tests::a_multi_argument_action_crosses_to_wsl_as_separate_arguments`, plus Tower Ubuntu WSL: `wsl.exe -d Ubuntu -- <cdx> config main` prints the settings, the old single-argument form does not — wave 4.
- request-AC11 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof: `tray/src/winterm.rs::tests::a_wsl_produced_candidate_list_is_replaced_by_what_windows_can_open` and `::only_terminals_present_on_this_host_are_offered`, against the real Tower reading (`['x-terminal-emulator']` from WSL; wt/powershell/cmd and no pwsh on Windows) — wave 4.
- request-AC11 -> This task. Proof: `tray/src/winterm.rs::tests::a_wsl_produced_candidate_list_is_replaced_by_what_windows_can_open` and `::only_terminals_present_on_this_host_are_offered`, against the real Tower reading (`['x-terminal-emulator']` from WSL; wt/powershell/cmd and no pwsh on Windows) — wave 4.
- request-AC12 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof: `tray/src/winterm.rs::tests::a_cmd_preference_runs_the_command_instead_of_opening_an_idle_shell`, plus Tower Windows: `cmd.exe /k "wsl.exe -d Ubuntu -- <cdx> config main"` runs it, `-NoExit -Command` does not — wave 4.
- request-AC12 -> This task. Proof: `tray/src/winterm.rs::tests::a_cmd_preference_runs_the_command_instead_of_opening_an_idle_shell`, plus Tower Windows: `cmd.exe /k "wsl.exe -d Ubuntu -- <cdx> config main"` runs it, `-NoExit -Command` does not — wave 4.
- request-AC13 -> This task. Proof: Final wave: `python3 -m pytest -q` 1,023 passed; `npm run lint` all checks passed; `cargo test --manifest-path tray/Cargo.toml` 104 passed; `cargo check --target x86_64-pc-windows-msvc` clean; `logics-manager lint`/`audit` OK; scoped Tower Windows and Ubuntu WSL checks recorded under Validation.

# Validation
- Wave 1 (item_147, credentials and portable backups): merge into a keychain-only profile now resolves the
- Python 1,023 passed; npm run lint OK; cargo test 104 passed; cargo check --target x86_64-pc-windows-msvc clean; Logics lint/audit OK; scoped Tower Windows + Ubuntu WSL checks confirmed AC10-AC12 read-only.
- Finish workflow executed on 2026-09-07.
- Linked backlog/request close verification passed.
  bundle-credential collision at the credential backend and reports the retained local account; a force import that
  fails after credential staging restores the keychain entry alongside files, record, and state, and names Claude
  keychain authentication when recovery is incomplete; encrypted bundles decode with the KDF their exporter recorded,
  with legacy (KDF-less) bundles still accepted through either derivation.
  Focused regressions: `test_merge_into_a_keychain_only_profile_keeps_the_local_account`,
  `test_late_force_import_failure_restores_the_original_credential`,
  `test_force_import_reports_a_credential_it_could_not_restore`,
  `test_encrypted_bundles_decode_with_the_kdf_their_exporter_recorded`.
  `python3 -m pytest -q`: 1,019 passed. `npm run lint`: all checks passed.
- Wave 2 (item_148, accepted local writes and run processes): memory appends serialize their read-modify-write per
  context path, so concurrent accepted notes all survive; the detached child names the top-level CLI module and the
  import root that contains it, and refuses to launch when that module does not resolve; an interrupted headless run
  terminates and reaps its provider process group and settles the registry as `cancelled` with exit code 130 and
  error code `run_cancelled`.
  Focused regressions: `test_concurrent_appends_keep_every_accepted_note`,
  `test_detached_child_runs_the_cli_module_and_records_a_terminal_result` (real detached child reaching a synthetic
  provider on PATH), `test_detached_child_command_names_the_top_level_cli_module`,
  `test_interrupting_a_headless_run_kills_the_provider_and_records_cancellation` (real child process, real
  terminate/reap).
  Each regression was confirmed to fail against the pre-fix behaviour before being kept.
  `python3 -m pytest -q`: 1,020 passed. `npm run lint`: all checks passed.
- Wave 3 (item_149, recoverable tray installation and probes): a promotion that fails between the two renames puts
  the proven companion back and reports a `TrayInstallError`, so `align_companion` restarts the tray it stopped; the
  Windows shortcut is written by the promotion against the final executable rather than by staging against the path
  that is about to move, and it stays in the install record's owned paths; the macOS staged probe runs the binary
  inside the app bundle, refuses a bundle with nothing runnable in it, and separates a launch failure (exec codes,
  death by signal) from a diagnostic that ran and reported a problem.
  Focused regressions: `test_a_promotion_failure_keeps_a_valid_installed_path_and_restarts_the_tray`,
  `test_an_update_points_the_shortcut_at_the_live_executable_and_keeps_owning_it`,
  `test_the_staged_probe_runs_the_companion_and_refuses_an_unusable_bundle`.
  All three were confirmed to fail against the pre-fix behaviour before being kept.
  `python3 -m pytest -q`: 1,023 passed. `npm run lint`: all checks passed.
  Rust tray tests and the native Windows/WSL checks are pending: no Rust toolchain is installed on this host, and
  those belong to the wave 4 slice that changes `tray/src/`.
- Wave 4 (item_150, Windows-to-WSL tray command and terminal interop): tray-launched CDX commands are argv parts,
  so a WSL crossing keeps `config <session>` as two arguments; the command construction moved to a new
  platform-neutral `tray/src/winterm.rs` so `cargo test` covers the Windows argv shapes on any host; a Windows tray
  offers only the terminals its own host can launch and falls back to the default console for a stored preference it
  cannot open; a `cmd` preference runs `cmd /k <command>` instead of PowerShell's `-NoExit -Command`.
  Focused regressions (Rust): `winterm::tests::a_multi_argument_action_crosses_to_wsl_as_separate_arguments`,
  `::windows_terminal_keeps_the_cdx_arguments_separate_across_wsl`,
  `::a_cmd_preference_runs_the_command_instead_of_opening_an_idle_shell`,
  `::powershell_still_takes_a_command_string`, `::a_terminal_this_companion_cannot_launch_has_no_command`,
  `::only_terminals_present_on_this_host_are_offered`,
  `::a_wsl_produced_candidate_list_is_replaced_by_what_windows_can_open`,
  `::a_supported_stored_preference_survives_the_restriction`.
- Final validation wave: `python3 -m pytest -q` 1,023 passed; `npm run lint` all checks passed;
  `cargo test --manifest-path tray/Cargo.toml` 104 passed; `cargo check --target x86_64-pc-windows-msvc` clean
  (the Windows-only loop compiles; its two dead-code warnings in `notify.rs` predate this work);
  `cargo clippy` reports nothing new for `win.rs` or `winterm.rs`; `logics-manager lint`/`audit` OK.
- Scoped Tower verification (read-only, operator-authorized host `aagos@kdesktop`):
  `wsl.exe -d Ubuntu -- <cdx> config main` prints the launch settings, while the single-argument form the tray used
  to build still answers `Unknown session: config main` (AC10);
  `cmd.exe /k "wsl.exe -d Ubuntu -- <cdx> config main"` runs the command, while `cmd.exe -NoExit -Command ...`
  fails with `'dx' is not recognized` (AC12);
  `cdx tray status --json` from Ubuntu WSL still advertises `['x-terminal-emulator']` while the Windows host has
  `wt.exe`, `powershell.exe` and `cmd.exe` but no `pwsh.exe` — the exact set the new restriction resolves to (AC11).
  No provider generation, no credential mutation, and no fleet state was changed.

# Report
- Not started.
- Finished on 2026-09-07.
- Linked backlog item(s): `item_147_preserve_credentials_and_portable_encrypted_backups`, `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`, `item_149_make_tray_installation_and_probes_recoverable`, `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`
- Related request(s): `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`

# Links
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
