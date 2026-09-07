## req_073_review_findings_credential_import_safety_bundle_portability_and_concurrent_memory - Review findings: data integrity, process lifecycle, and tray updates
> From version: 0.20.9
> Schema version: 1.0
> Status: Draft
> Understanding: 95
> Confidence: 95
> Complexity: Medium
> Theme: Data integrity and portability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: Twelve reproduced defects affect credential imports, bundle portability, concurrent memory, detached execution, process cancellation, tray updates, and Windows-to-WSL tray actions.
- Keywords: review, credential, import, bundle, memory, detached, cancellation, tray, shortcut, rollback, WSL, terminal
- Use when: Evaluating follow-up work on data integrity, subprocess lifecycle, or tray update guarantees.
- Skip when: Implementing unrelated provider features or presentation changes.

# Needs
- P1: Preserve the existing local keychain account during an import in merge mode.
- P1: Preserve or recover the original keychain credential when a force import fails after writing imported credentials.
- P2: Decode encrypted bundles with the KDF recorded by the exporter, independent of the importing runtime's capabilities.
- P2: Preserve both notes when multiple agents append to the same memory scope concurrently.
- P1: Make the detached child execute an existing CLI module from the correct package root.
- P1: Terminate and reap headless provider processes when the supervising run is interrupted.
- P2: Make tray promotion failures restore the previous executable and restart a previously running companion.
- P2: Keep the native Windows shortcut pointed at the final installed executable across tray updates.
- P2: Make the macOS staged-companion probe actually execute the companion and reject launch failures.
- P2: Make Windows-to-WSL tray configuration actions pass `cdx config <session>` as separate arguments.
- P2: Make a Windows tray using WSL advertise Windows-launchable terminals, not Linux-only terminal candidates from inside WSL.
- P2: Make the Windows `cmd` terminal preference run WSL commands through `cmd /k` rather than PowerShell-style flags.
- This request captures review candidates only; no implementation or delivery chain is committed.

# Priority
- High: authentication can be lost, detached execution fails before reaching the provider, and cancelled headless work can continue outside its supervisor.

# Context
- Reviewed commit: `8ea68b1ad47947f3af6e71072193cc34846585d6`, on 2026-09-07. The working tree was initially clean.
- Inspected profile lifecycle and credential integration, bundle import/export, session and run persistence, context memory, process/failover helpers, update handling, viewer delegation, tray polling, packaging, and CI. This is a targeted repository review, not an exhaustive audit of every source line or a live cross-platform qualification.
- Existing corpus checks reported zero open workflow documents and zero health issues. Reviewed the prior profile-safety requests and repository reliability review to distinguish remaining gaps from delivered fixes. The earlier merge rollback fix covers files and metadata; the findings here concern keychain precedence and recovery introduced by credential portability. Prior context-memory coverage work does not capture concurrent append loss. Searches for KDF and PBKDF returned no matches.

## Finding 1: Merge replaces a keychain-only local account (P1)
- Evidence: `src/session_backup.py:367` protects only existing filesystem paths. A keychain-only profile has no credential file, so the bundle credential is written at line 371 and the local keychain entry is deleted at line 374, even in merge mode.
- Reproduction: export an encrypted bundle from a synthetic profile using account A; change that profile's simulated keychain to account B without adding a credential file; import the bundle with `merge=True`. The command succeeds, the keychain entry for B disappears, and the credential file contains A.
- Impact: an operation intended to retain local values silently switches the session's account and removes its existing authentication. The collision exists at the credential-backend level even though the file path is absent.
- Coverage gap: merge tests protect existing files and state; keychain import tests exercise fresh and force imports, not a merge into a keychain-only destination.

## Finding 2: Force-import rollback loses the original keychain credential (P1)
- Evidence: `src/session_backup.py:374` deletes the destination keychain before `_restore_force_import_profile_paths` at line 375, which can still fail while copying plugins. The handler at line 378 calls `_restore_import_backup`, whose implementation at line 163 restores only files, the record, and state.
- Reproduction: start with a keychain-only profile, a distinct encrypted bundle credential, and a local plugin sentinel. Inject an OSError from the plugin `shutil.copytree` during `force=True` import. The original record and plugin sentinel are restored, but the original keychain entry is absent and the imported credential file has been removed by rollback.
- Impact: a failed import permanently loses the profile's sole local credential while completing its filesystem rollback. Recovery files are subsequently removed, and no credential snapshot exists.
- Coverage gap: rollback checks do not inject a failure after successful destination keychain deletion.

## Finding 3: Bundle decryption ignores the stored KDF (P2)
- Evidence: `src/backup_bundle.py:117` records `scrypt` or `pbkdf2-hmac-sha256`, but decode at line 142 calls `_derive_aead_key` without that field. `_derive_keys` at line 55 chooses again from the current runtime's `hashlib.scrypt` availability. The legacy decoder at line 149 uses the same helper.
- Reproduction: use the encoder with a simulated hashlib that exposes PBKDF2 but no scrypt. The encrypted bundle decrypts successfully in that environment and advertises `pbkdf2-hmac-sha256`. Restore the normal runtime with scrypt and decode the identical bytes with the identical passphrase: it raises `Invalid bundle passphrase or corrupted bundle.`
- Impact: a valid backup can become unreadable after moving machines or changing the Python runtime, even though its declared KDF is supported by the destination. This is a portability failure, not evidence of cryptographic compromise.
- Coverage gap: same-runtime round trips never exercise exporter/importer capability differences.

## Finding 4: Concurrent memory appends silently lose a note (P2)
- Evidence: `src/context_store.py:112` reads the whole file before constructing and replacing its contents at line 114, with no lock covering the read-modify-write. `src/commands/context_memory.py:333` routes CLI memory appends through this helper for every scope.
- Reproduction: start a temporary context with an initial line; use two workers and a barrier after both real reads, then append distinct notes through `append_context_path`. Both operations return success, but only one note remains. The barrier controls scheduling only; the actual file reads and atomic writes run unchanged.
- Impact: parallel agents sharing workspace, global, or named-project memory can erase one another's accepted notes. Atomic replacement prevents torn files but not lost updates.
- Coverage gap: existing append tests are sequential.

## Finding 5: Detached runs invoke a module that does not exist (P1)
- Evidence: `src/commands/runs.py:152` builds `python -m {__package__}.cli`. Since this function moved under `commands`, the result is `src.commands.cli` for source/npm installs, or `cdx_manager.commands.cli` for a Python installation; neither module exists. The computed package root at line 151 also stops at `src` rather than its import parent. `_spawn_detached_run` uses these values at line 229.
- Reproduction: call the actual CLI `main` with an isolated authenticated fixture and `--detach`, preserving the fixture's authentication probe but using a real Popen for the detached Python child. The parent returns exit zero and `ok: true`; the child exits nonzero and its launch log reports failure to import `src.commands.cli`. Executing the constructed command from the correct repository root also fails, confirming the module name is independently wrong.
- Reproduced on macOS and native Windows using the exact reviewed source snapshot. No provider generation was launched.
- Impact: the default detached path reports a launched run that never executes the task. Cleanup normally performed by the child, including removal of the staged prompt, is never reached.
- Coverage gap: detached tests inject a successful child object and inspect argv but never execute the selected module. The packaged smoke workflows do not run a detached task.

## Finding 6: Interrupting a headless run leaves its provider alive (P1)
- Evidence: `src/provider_runtime.py:1031` starts the provider in its own POSIX session. The wait at line 1051 handles TypeError and TimeoutExpired only; there is no interruption cleanup. Neither `handle_run` nor `cli_entry` catches KeyboardInterrupt to terminate the child or settle the registry.
- Reproduction: substitute only the launch specification with a harmless Python process that writes its PID to a temporary file and sleeps. Keep the actual Popen and wait path; send SIGINT to the supervisor after the child starts. The call raises KeyboardInterrupt, but `os.kill(child_pid, 0)` confirms the child is still alive. The reproduction explicitly kills and reaps its child afterwards.
- Impact: Ctrl-C stops the supervising CLI on POSIX while the provider can continue consuming quota or modifying workspace files. The run record still describes the supervisor's lifecycle rather than a completed cancellation.
- Coverage gap: timeout tests do not exercise actual SIGINT delivery to the headless supervisor. This finding was exercised on macOS, not native Windows signal handling.

## Finding 7: Tray promotion failure leaves the installed path missing (P2)
- Evidence: `src/tray_install.py:448` renames the working directory to `companion.previous`, then line 449 promotes staging without a rollback guard. `align_companion` catches only TrayInstallError at line 297, so an OSError from promotion bypasses its restart path. The maintenance wrapper catches the error but cannot restore the moved executable.
- Reproduction: install a synthetic checksummed tray archive in a temporary home; call `align_companion` with a simulated previously running tray and inject OSError only on staging-to-live rename. The recorded executable no longer exists, the previous copy remains retired, install metadata still points at the missing live path, and the restart callback is never called.
- Impact: an update-time filesystem error leaves a stopped tray with a broken launch/autostart path until manual recovery, despite retaining a recoverable previous directory.
- Coverage gap: existing alignment tests cover download/probe/restart failures, not a failure between the two renames.

## Finding 8: Windows tray update leaves a broken native shortcut (P2)
- Evidence: `src/tray_install.py:229` calls `create_shortcut` even for `record=False` staging installs. The staging executable is later moved to live, but only the JSON executable field is rewritten at line 457. Line 458 also replaces the owned-path list with `[live]`, dropping the shortcut from uninstall ownership.
- Reproduction on native Windows: redirect APPDATA, LOCALAPPDATA, USERPROFILE, HOME, and CDX_HOME into a temporary area; install then update a synthetic checksummed archive, with only the executable launch probe substituted. Both calls use the real PowerShell/COM shortcut writer. Read the binary .lnk through WScript.Shell afterwards: TargetPath contains `companion.staged`, that path is absent, and the shortcut is missing from the new state's `paths` list.
- Impact: the Start Menu entry points at a moved executable after a successful update and is no longer removed by uninstall. Toast display behavior was not tested, so no claim of observed notification loss is made.
- Coverage gap: existing tests verify shortcut creation and companion replacement separately, not the final native shortcut target after promotion.

## Finding 9: macOS staged-companion probe reports success without starting it (P2)
- Evidence: `src/tray_install.py:504` appends `--print` to `launch_command`, which returns `open -a <bundle>` for an app. Thus `--print` reaches the macOS open utility rather than the companion. The probe ignores the process exit status and returns True at line 509.
- Reproduction: invoke the real probe on a nonexistent temporary `.app` path under macOS. Capture the actual subprocess call and result: argv is `open -a <path> --print`, open exits nonzero, and `_probe` still returns True. No application is opened.
- Impact: the documented pre-promotion launch gate cannot detect an unusable app bundle. In the no-running-tray case there is no subsequent restart validation, so the update can claim alignment without having run the replacement at all.
- Coverage gap: update tests normally inject `probe=lambda ...: True`; they do not exercise the native open command's argument handling.

## Finding 10: Windows-to-WSL tray configuration opens the session, not its config (P2)
- Evidence: `tray/src/win.rs:182` passes `format!("config {name}")` as one `arg`. `open_terminal` and the Windows Terminal WSL path pass that string as a single argv element to `wsl.exe -- cdx`, so CDX receives one session name named `config work1` instead of the `config` subcommand plus `work1`.
- Reproduction on Tower WSL: `wsl.exe -d Ubuntu -- cdx 'config work1'` reports `Unknown session: config work1`; `wsl.exe -d Ubuntu -- cdx config work1` prints the launch settings.
- Impact: clicking a session's "Launch settings" row from a Windows tray configured for WSL opens a failing command instead of the session configuration.
- Coverage gap: existing menu tests assert the action id, but no Windows-to-WSL test executes or inspects the final argv shape for multi-word CDX subcommands.

## Finding 11: Windows tray using WSL offers Linux terminal choices that cannot open (P2)
- Evidence: `src/commands/tray.py:143` serializes `terminal_candidates()` from the environment that runs `cdx tray status`. Under Windows-to-WSL transport that environment is Linux, so `src/tray_terminal.py:70` returns Linux candidates. The Windows handler in `tray/src/win.rs:341` recognizes only `powershell`, `pwsh`, and `cmd`, with a special `wt` path at line 320; any other selected preference logs unavailable and does not fall back.
- Reproduction on Tower WSL: `cdx tray status --json` returned `terminal_candidates: ['x-terminal-emulator']`. Native Windows on the same host has `wt.exe`, PowerShell, and `cmd.exe`; `pwsh` is absent.
- Impact: the Windows tray can present a Linux terminal preference that the Windows companion cannot launch, and selecting it makes session/config clicks inert.
- Coverage gap: tests cover Linux and Windows terminal candidate generation separately, not the cross-transport contract where a Windows UI consumes a WSL-produced snapshot.

## Finding 12: Windows `cmd` preference receives PowerShell flags for WSL commands (P2)
- Evidence: `tray/src/win.rs:341` groups `cmd` with PowerShell-like terminals, then line 345 sends `-NoExit -Command ...` for WSL transport before the native `cmd /k` branch at line 347 can apply. `cmd.exe` does not run that command shape.
- Reproduction on Tower Windows: `cmd.exe -NoExit -Command echo hi` opens a prompt without executing `echo hi`; `cmd.exe /k echo hi` prints `hi`. The same branch would be used for a `cmd` preference with `CDX_TRAY_WSL=1`.
- Impact: even if the user manually records `cmd` as a terminal preference, WSL-backed tray actions open an idle shell instead of running the selected CDX action.
- Coverage gap: no Rust test covers preferred terminal command construction for Windows-to-WSL with `cmd`.

## Validation observed
- `rtk npm run lint`: passed (documentation checks, Ruff, JavaScript syntax, Python compilation).
- `rtk npm test`: 1,012 Python tests passed in 23.83 seconds.
- `rtk cargo test --manifest-path tray/Cargo.toml`: 96 Rust tests passed.
- `rtk npm pack --dry-run`: passed.
- A temporary stdlib reproduction script executed with `node bin/python-runner.js` reproduced all four findings and asserted their resulting state. It reused the existing profile-safety fixture's simulated keychain; no live credentials or provider sessions were touched. The first invocation encountered a test-module import-path error, corrected before the successful run.
- Continued review on the same commit reproduced findings 5-9 with a second temporary Python script. It used real detached Python children, actual SIGINT delivery, temporary tray archives, an injected promotion error, and the real macOS open utility. Synthetic subprocesses were terminated and reaped.
- Native Windows verification used Python 3.10.4 over SSH on the operator-authorized desktop and the exact source snapshot transferred to a temporary directory. Both detached-child failure and the native .lnk target defect reproduced. Targeted pytest invocation: `python -m pytest -q test/test_commands_runs_py.py test/test_provider_runtime_helpers_py.py`; 92 passed, 1 skipped, and 10 subtests passed. This is not the full Windows suite or a packaged-install test.
- The initial Windows harness completed its checks but failed during temporary-directory cleanup because its own cwd was inside the directory. The harness was corrected to leave that directory before cleanup; this was a review-script issue, not an application finding.
- Tower WSL verification used Ubuntu WSL2 through the Windows SSH landing zone. `cdx tray status --json` returned Linux terminal candidates to the Windows tray path; direct interop commands reproduced the single-argument `config work1` failure; native Windows command checks confirmed the `cmd.exe -NoExit -Command` shape does not execute the requested command. `cdx configs --json` and `cdx tray status --json` were read-only.
- Linux execution was limited to WSL command paths and the prior Python test run reported in the source session; live keychain round trips and installation of built distribution packages were not performed. Dependency vulnerability scanning and release readiness are not claimed.
- Application source and existing tests remain unchanged. Repository changes are confined to this review capture and any index output required by the workflow.

# Acceptance criteria
- AC1: Merging an auth-bearing bundle into a keychain-only profile preserves the existing local account without deleting its credential.
- AC2: A failed force import after credential staging restores the original authentication as well as profile files, record, and state; incomplete recovery is reported explicitly.
- AC3: An encrypted bundle created through the PBKDF2 fallback decodes on a runtime with scrypt using the correct passphrase; decoding follows a validated recorded KDF and defines compatibility for legacy bundles.
- AC4: Two successful concurrent appends to the same memory scope retain both notes and the pre-existing content.
- AC5: Any selected fixes include focused regressions for these cases, and the Python/Rust suites and lint continue to pass.
- AC6: A real detached child resolves and runs the correct CLI module for source/npm and Python-package layouts, reaches a synthetic provider, and records a terminal result.
- AC7: Interrupting a headless run terminates and reaps its owned provider process and records cancellation rather than leaving work running.
- AC8: A failure while promoting the staged tray preserves or restores the installed path and restarts the previous companion when it was running.
- AC9: After a successful or failed tray update, the Windows shortcut points at the valid installed executable and remains covered by uninstall ownership.
- AC10: The macOS staged probe actually invokes the companion, distinguishes launch failure from a valid diagnostic exit, and refuses an unusable bundle before promotion.
- AC11: Windows-to-WSL tray actions that need multiple CDX arguments, including session config, execute the intended subcommand in a real WSL distribution.
- AC12: A Windows tray using WSL shows only terminal preferences the Windows companion can launch, and an unsupported stored preference falls back to a working default.
- AC13: A `cmd` terminal preference with WSL transport executes the selected CDX command through `cmd /k` or an equivalent verified command form.

# Definition of Ready (DoR)
- [ ] Problem statement is explicit and user impact is clear.
- [ ] Scope boundaries (in/out) are explicit.
- [ ] Acceptance criteria are testable.
- [ ] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/session_backup.py`
- `src/backup_bundle.py`
- `src/claude_credentials.py`
- `src/context_store.py`
- `src/commands/context_memory.py`
- `test/test_profile_data_safety_py.py`
- `test/test_session_service_py.py`
- `test/test_context_store_py.py`
- `src/commands/runs.py`
- `src/provider_runtime.py`
- `src/tray_install.py`
- `src/tray_shortcut.py`
- `tray/src/win.rs`
- `tray/src/snapshot.rs`
- `src/tray_terminal.py`
- `test/test_commands_runs_py.py`
- `test/test_provider_runtime_helpers_py.py`
- `test/test_tray_capability_py.py`

# Backlog
- none
