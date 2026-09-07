## task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop - Orchestrate review finding hardening across credentials, runs, and tray interop
> From version: 0.20.9
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 50%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:39:34
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
- [ ] 3. Then repair tray installation, shortcut, and macOS probe recovery without changing tray feature scope.
- [ ] 4. Finish with Windows-to-WSL tray argv and terminal interop, including Tower smoke checks.
- [ ] 5. For each slice, add the smallest focused regressions, run targeted tests first, then Python/Rust suites, lint, Logics validation, and scoped Tower verification before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_147_preserve_credentials_and_portable_encrypted_backups`
- `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`
- `item_149_make_tray_installation_and_probes_recoverable`
- `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof deferred to slice closeout.
- request-AC2 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof deferred to slice closeout.
- request-AC3 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof deferred to slice closeout.
- request-AC13 -> `item_147_preserve_credentials_and_portable_encrypted_backups`. Proof deferred to slice closeout.
- request-AC4 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof deferred to slice closeout.
- request-AC5 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof deferred to slice closeout.
- request-AC6 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof deferred to slice closeout.
- request-AC13 -> `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`. Proof deferred to slice closeout.
- request-AC7 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof deferred to slice closeout.
- request-AC8 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof deferred to slice closeout.
- request-AC9 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof deferred to slice closeout.
- request-AC13 -> `item_149_make_tray_installation_and_probes_recoverable`. Proof deferred to slice closeout.
- request-AC10 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof deferred to slice closeout.
- request-AC11 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof deferred to slice closeout.
- request-AC12 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof deferred to slice closeout.
- request-AC13 -> `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`. Proof deferred to slice closeout.

# Validation
- Wave 1 (item_147, credentials and portable backups): merge into a keychain-only profile now resolves the
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

# Report
- Not started.

# Links
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
