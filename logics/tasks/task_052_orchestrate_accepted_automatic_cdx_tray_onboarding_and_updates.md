## task_052_orchestrate_accepted_automatic_cdx_tray_onboarding_and_updates - Orchestrate accepted automatic CDX tray onboarding and updates
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 92%
> Confidence: 78%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus
> Indicators reviewed: 2026-08-11 12:48:55

# AI Context
- Summary: Orchestrate accepted automatic CDX tray onboarding and updates
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- `src/tray_install.py:391` already performs the rename-live-to-retired then promote-staged sequence, which is the documented Windows-safe order. What it has never faced is a companion that is running.
- Settled by measurement after delivery, on Windows 11 26200: renaming a directory that holds a running executable **succeeds**. The expectation recorded here — that an image section would lock the parent directory and fail with ERROR_ACCESS_DENIED — was wrong. What Windows refuses is deleting or overwriting a running executable, which is why the rename-to-delete pattern exists at all. Nothing was built on the wrong expectation, because the transaction stops the companion first regardless; but the reason it holds is not the one written here, and adr_005 now carries the measured version.
- MoveFileEx with MOVEFILE_DELAY_UNTIL_REBOOT is the last-resort disposal for a retired directory that still cannot be removed. Ordinary cleanup happens at the next start, not inside the transaction.
- There is no shutdown channel to use. `tray/src/instance.rs` holds a pid file and a liveness probe only, so "request a bounded graceful shutdown" is a mechanism this task introduces.
- A flag file under `runtime_dir()`, polled by the loop that already wakes every 100 ms, is preferred to a signal: it behaves identically on the three platforms and avoids Windows thread-message and handle ownership questions.
- The timeout has to tolerate an open menu. adr_006 records that TrackPopupMenu is modal, so a Windows companion showing its menu processes nothing until the user dismisses it. The bounded wait fails with a message naming that cause; it never escalates to a kill.
- Restoring the retired companion is not enough on failure: it must also be relaunched, or the rollback leaves a healthy binary and no running tray.

# Plan
- [x] 1. Trace install flags and prompts, session creation defaults, notification preference persistence, provider provisioning, companion instance detection, autostart artifacts, and update staging end to end.
- [x] 2. Define the smallest explicit consent state and deterministic non-interactive flags; apply accepted alert intent to existing and future supported sessions while surfacing provider trust boundaries.
- [x] 3. Reproduce the Windows directory rename against a running companion first, then implement the update transaction on what it shows: request bounded graceful shutdown through a polled flag file, promote the verified replacement, relaunch it, and on failure restore and relaunch the proven companion.
- [x] 4. Add targeted tests for all consent and restart outcomes, update README and diagnostics, then run project and Logics validation plus native smoke checks where available.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `_tray_install` asks autostart and alerts through two separate `_accepted` calls with their own flag pairs; declining one leaves the other untouched, per `test_declining_one_question_leaves_the_other_untouched` (b875465).
- request-AC2 -> This task. Proof: `_enable_alerts_everywhere` sets notify on every supported session and records the tray-owned default that `_launch_defaults_for` reads at session creation; unsupported providers are skipped. Covered by `test_accepting_alerts_covers_every_supported_session_and_leaves_others_alone` and `test_a_session_created_later_inherits_the_accepted_default` (b875465).
- request-AC3 -> This task. Proof: the JSON result carries `started`, `autostart`, `alerts`, `alerts_sessions` and `codex_trust_required`, and the text output says each; `test_a_non_interactive_or_json_run_declines_rather_than_deciding` and `test_an_explicit_flag_is_never_a_prompt` pin that no script is ever prompted (b875465).
- request-AC4 -> This task. Proof: `align_companion` stages, verifies, promotes and restarts; with no tray running it updates the files and starts nothing, asserted by `test_a_drifted_companion_is_moved` and `test_a_running_companion_is_stopped_replaced_and_started_again` (36a4800).
- request-AC5 -> This task. Proof: only a live CDX instance is acted on — a stale lock is not one (`test_a_stale_lock_is_not_a_running_companion`); the wait is bounded and never escalates to a kill (`test_a_companion_that_ignores_the_request_is_left_alone`); a start counts only once the replacement registers its lock (`test_a_launch_that_never_registers_is_not_a_start`); and a failed replacement is rolled back and the proven companion restarted (`test_a_replacement_that_does_not_start_is_rolled_back_and_the_old_one_restarted`) (36a4800).
- request-AC6 -> This task. Proof: `cdx update` prompts for nothing, the promotion keeps the live directory name so a recorded login item still resolves, and the defaults file is untouched. Covered by `test_an_update_keeps_the_login_item_pointing_at_a_live_path` and `test_an_update_does_not_touch_the_accepted_alert_default`; `cdx tray autostart off` and the alert mute remain independent commands (b875465).
- request-AC7 -> This task. Proof: 822 Python tests and 67 tray tests pass, ruff clean, and the tray builds and lints on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu. The staged-asset safety path is unchanged and still covered by the existing extraction and checksum tests (b875465).

# Validation
- (no validation recorded yet)
- command: `python3 -m pytest (822 passed), ruff, cargo test (67 passed), cargo clippy on the macOS/Windows/Linux targets` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`
- Related request(s): `req_041_make_accepted_cdx_tray_onboarding_and_updates_automatic`

# Links
- Request: `req_041_make_accepted_cdx_tray_onboarding_and_updates_automatic`
- Product brief(s): `prod_030_accepted_automatic_cdx_tray_experience`
- Architecture decision(s): (none yet)
