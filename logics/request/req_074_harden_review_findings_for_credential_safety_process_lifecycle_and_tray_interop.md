## req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop - Harden review findings for credential safety, process lifecycle, and tray interop
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:59:27

# AI Context
- Summary: Development-ready hardening chain for all twelve req_073 review findings across credential import, encrypted bundle portability, concurrent memory, detached/headless run lifecycle, tray update recovery, and Windows-to-WSL tray interop.
- Keywords: req_073, review findings, credential import, keychain rollback, bundle KDF, concurrent memory, detached run, SIGINT cleanup, tray update, Windows shortcut, macOS probe, WSL tray
- Use when: Planning or implementing fixes for the review findings captured in req_073.
- Skip when: The work is unrelated to credential safety, run lifecycle, local memory writes, tray update recovery, or Windows-to-WSL tray behavior.

# Needs
- Import and restore operations must preserve local credentials and bundle portability across supported Python runtimes.
- Accepted local writes and launched work must either complete under CDX supervision or fail without hidden work, lost memory, or false success.
- Tray updates and Windows-to-WSL actions must leave the user with a valid companion, valid shortcuts, and commands that run the intended CDX action.

# Context
- Review request req_073 reproduced twelve defects on the current source snapshot across macOS, Tower native Windows, and Tower Ubuntu WSL2.
- Credential import findings are rooted in keychain/file precedence and rollback boundaries in src/session_backup.py plus KDF selection in src/backup_bundle.py.
- Process findings are rooted in detached child module selection in src/commands/runs.py and interrupt cleanup in src/provider_runtime.py.
- Tray findings are rooted in staging promotion, native shortcut ownership, macOS launch probing, and Windows-to-WSL argument and terminal selection paths.
- The work must be implemented in small validated slices with focused regressions before broad suites; no live credentials, provider generations, or destructive fleet changes are required.

# Acceptance criteria
- AC1: Merging an auth-bearing bundle into a keychain-only profile preserves the existing local account without deleting its credential.
- AC2: A failed force import after credential staging restores the original authentication as well as profile files, record, and state; incomplete recovery is reported explicitly.
- AC3: An encrypted bundle created through the PBKDF2 fallback decodes on a runtime with scrypt using the correct passphrase; decoding follows a validated recorded KDF and defines compatibility for legacy bundles.
- AC4: Two successful concurrent appends to the same memory scope retain both notes and the pre-existing content.
- AC5: A real detached child resolves and runs the correct CLI module for source/npm and Python-package layouts, reaches a synthetic provider, and records a terminal result.
- AC6: Interrupting a headless run terminates and reaps its owned provider process and records cancellation rather than leaving work running.
- AC7: A failure while promoting the staged tray preserves or restores the installed path and restarts the previous companion when it was running.
- AC8: After a successful or failed tray update, the Windows shortcut points at the valid installed executable and remains covered by uninstall ownership.
- AC9: The macOS staged probe actually invokes the companion, distinguishes launch failure from a valid diagnostic exit, and refuses an unusable bundle before promotion.
- AC10: Windows-to-WSL tray actions that need multiple CDX arguments, including session config, execute the intended subcommand in a real WSL distribution.
- AC11: A Windows tray using WSL shows only terminal preferences the Windows companion can launch, and an unsupported stored preference falls back to a working default.
- AC12: A cmd terminal preference with WSL transport executes the selected CDX command through cmd /k or an equivalent verified command form.
- AC13: Focused regressions, Python tests, Rust tray tests, lint, Logics validation, and scoped Tower Windows plus Ubuntu WSL checks pass before closeout.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)

# References
- logics/request/req_073_review_findings_credential_import_safety_bundle_portability_and_concurrent_memory.md
- src/session_backup.py
- src/backup_bundle.py
- src/context_store.py
- src/commands/runs.py
- src/provider_runtime.py
- src/tray_install.py
- src/tray_shortcut.py
- tray/src/win.rs
- tray/src/snapshot.rs
- src/tray_terminal.py

# Backlog
- `item_147_preserve_credentials_and_portable_encrypted_backups`
- `item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx`
- `item_149_make_tray_installation_and_probes_recoverable`
- `item_150_repair_windows_to_wsl_tray_command_and_terminal_interop`
