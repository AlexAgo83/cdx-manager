## task_049_orchestrate_trustworthy_cdx_tray_operation_and_platform_validation - Orchestrate trustworthy CDX tray operation and platform validation
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 35%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: claude

# AI Context
- Summary: Orchestrate trustworthy CDX tray operation and platform validation
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Blocked on task_046: this task hardens the companion that task_046 builds. Do not start it while task_046 is open.
- This is a release gate, not a later polish pass. No tray release ships before these lifecycle, single-instance, and diagnostic controls exist, so it runs immediately after task_046 and ahead of task_047 and task_048 if capacity forces a choice.

# Plan
- [ ] 1. Implement and test lifecycle, single-instance, capacity, privacy, and recovery controls without enabling anything by default.
- [ ] 2. Implement WSL source selection and Linux capability boundaries, then run scoped managed-host smoke checks.
- [ ] 3. Verify that alert and plugin integrations retain their own limits, document support and recovery, and run project plus workflow validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`
- `item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`. Proof deferred to slice closeout.
- request-AC2 -> `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`. Proof deferred to slice closeout.
- request-AC4 -> `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`. Proof deferred to slice closeout.
- request-AC5 -> `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`. Proof deferred to slice closeout.
- request-AC6 -> `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`. Proof deferred to slice closeout.
- request-AC8 -> `item_084_add_explicit_cdx_tray_lifecycle_capacity_privacy_and_recovery_controls`. Proof deferred to slice closeout.
- request-AC3 -> `item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts`. Proof deferred to slice closeout.
- request-AC7 -> `item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts`. Proof deferred to slice closeout.
- request-AC8 -> `item_085_constrain_wsl_and_linux_tray_support_and_validate_it_on_real_hosts`. Proof deferred to slice closeout.

# Validation
- Autostart and doctor wave: `python3 -m pytest -q` 713 passed, ruff clean. Exercised for real on macOS: the on/off/idempotence cycle writes and removes a LaunchAgent plist, and `cdx tray doctor` reports companion, executable, version, instance and autostart in one table.
- Single-instance wave: `cargo test` 24 passed, `cargo clippy -- -D warnings` clean on all three targets. Verified with the signed bundle on the arm64 macOS host: a second launch exits 3 naming the first companion's pid, and a pid file left by a killed companion is reclaimed by the next launch rather than blocking it.

# Report
- Single-instance lock delivered in `tray/src/instance.rs`, taken before any backend draws. Two icons in the menu bar is the worst failure this feature has, because both are correct and the user cannot tell which to quit.
- The lock records a pid rather than merely existing. A presence-only lock would outlive a crash and leave the tray unstartable until someone found and deleted the file, which is worse than the failure it prevents. A dead or truncated pid reads as stale and is reclaimed.
- A recycled pid would read as alive and cost a refused launch rather than a duplicate icon. That is the safe direction to be wrong in, and it is why the check is `kill(pid, 0)` rather than something cleverer.
- Autostart is off until asked, and its state is read back from the platform rather than remembered. A recorded intention that drifted from the system is exactly the confusion doctor exists to end, so doctor must not consult the same memory that could be wrong.
- No `KeepAlive` in the LaunchAgent: quitting the tray from its own menu has to mean quit, not be restarted by launchd a second later.
- `cdx tray doctor` reads and never repairs. A doctor that also acted would have to be trusted with the machine; this one only has to be trusted to tell the truth, and a test asserts it creates nothing it reported as absent.
- The lock lives under the per-user temporary directory, not a shared path, so one user's companion cannot block another's on a shared machine.

# Links
- Request: `req_038_harden_cdx_tray_lifecycle_clarity_and_platform_validation`
- Product brief(s): `prod_027_trustworthy_cdx_tray_operation`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
