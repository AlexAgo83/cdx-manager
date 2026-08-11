## task_052_orchestrate_accepted_automatic_cdx_tray_onboarding_and_updates - Orchestrate accepted automatic CDX tray onboarding and updates
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 92%
> Confidence: 78%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Orchestrate accepted automatic CDX tray onboarding and updates
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- `src/tray_install.py:391` already performs the rename-live-to-retired then promote-staged sequence, which is the documented Windows-safe order. What it has never faced is a companion that is running.
- Open question to settle before anything else is written: the rename-to-delete pattern is documented for the executable file, but here it is the directory containing a running executable that moves. Windows holds an image section on that binary, so the directory rename is expected to fail with ERROR_ACCESS_DENIED. If it does, the shape of the transaction changes, so step 3 starts by reproducing it rather than by designing around it.
- MoveFileEx with MOVEFILE_DELAY_UNTIL_REBOOT is the last-resort disposal for a retired directory that still cannot be removed. Ordinary cleanup happens at the next start, not inside the transaction.
- There is no shutdown channel to use. `tray/src/instance.rs` holds a pid file and a liveness probe only, so "request a bounded graceful shutdown" is a mechanism this task introduces.
- A flag file under `runtime_dir()`, polled by the loop that already wakes every 100 ms, is preferred to a signal: it behaves identically on the three platforms and avoids Windows thread-message and handle ownership questions.
- The timeout has to tolerate an open menu. adr_006 records that TrackPopupMenu is modal, so a Windows companion showing its menu processes nothing until the user dismisses it. The bounded wait fails with a message naming that cause; it never escalates to a kill.
- Restoring the retired companion is not enough on failure: it must also be relaunched, or the rollback leaves a healthy binary and no running tray.

# Plan
- [ ] 1. Trace install flags and prompts, session creation defaults, notification preference persistence, provider provisioning, companion instance detection, autostart artifacts, and update staging end to end.
- [ ] 2. Define the smallest explicit consent state and deterministic non-interactive flags; apply accepted alert intent to existing and future supported sessions while surfacing provider trust boundaries.
- [ ] 3. Reproduce the Windows directory rename against a running companion first, then implement the update transaction on what it shows: request bounded graceful shutdown through a polled flag file, promote the verified replacement, relaunch it, and on failure restore and relaunch the proven companion.
- [ ] 4. Add targeted tests for all consent and restart outcomes, update README and diagnostics, then run project and Logics validation plus native smoke checks where available.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC2 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC3 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC4 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC5 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC6 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.
- request-AC7 -> `item_088_add_consented_tray_onboarding_defaults_and_safe_running_companion_restart`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_041_make_accepted_cdx_tray_onboarding_and_updates_automatic`
- Product brief(s): `prod_030_accepted_automatic_cdx_tray_experience`
- Architecture decision(s): (none yet)
