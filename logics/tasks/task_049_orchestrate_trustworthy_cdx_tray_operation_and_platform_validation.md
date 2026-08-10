## task_049_orchestrate_trustworthy_cdx_tray_operation_and_platform_validation - Orchestrate trustworthy CDX tray operation and platform validation
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 95%
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
- Hardware smoke wave, three hosts: 6/6 on kdesktop with the real 11-session fleet through Ubuntu WSL (60s period, poll cost 371-401ms so alert latency <= 61s), 5 pass and 1 justified skip with the Linux ksni build running natively in that same WSL (30s period, 140-145ms, and the absent-watcher path reported as `no org.kde.StatusNotifierWatcher ... this desktop has no system tray`), and 6/6 on macOS arm64 native at 88-92ms with polling stopped on an empty fleet. `cargo test` 30 passed, clippy clean on all three targets, `python3 -m pytest -q` 719 passed, ruff clean, Logics lint OK. Full record in `item_085`.
- Tooltip wave: `python3 -m pytest -q` 719 passed, 30 Rust tests, clippy clean on all three targets. The tooltip is composed by CDX and consumed identically by all three backends.
- WSL resolution wave: `cargo test` 30 passed, clippy clean on all three targets. Verified on kdesktop: a configured `Debian` reports `WSL distribution \`Debian\` is not installed. Installed: Ubuntu, docker-desktop-data, docker-desktop.`, and `Ubuntu` polls normally at 60s.
- Staged update wave: `python3 -m pytest -q` 716 passed, ruff clean. A replacement is downloaded, verified and proved to start before the working companion is touched; a probe that fails leaves the installed one running and cleans the staging away, and doctor reports an interrupted update.
- Autostart and doctor wave: `python3 -m pytest -q` 713 passed, ruff clean. Exercised for real on macOS: the on/off/idempotence cycle writes and removes a LaunchAgent plist, and `cdx tray doctor` reports companion, executable, version, instance and autostart in one table.
- Single-instance wave: `cargo test` 24 passed, `cargo clippy -- -D warnings` clean on all three targets. Verified with the signed bundle on the arm64 macOS host: a second launch exits 3 naming the first companion's pid, and a pid file left by a killed companion is reclaimed by the next launch rather than blocking it.

# Report
- Single-instance lock delivered in `tray/src/instance.rs`, taken before any backend draws. Two icons in the menu bar is the worst failure this feature has, because both are correct and the user cannot tell which to quit.
- The lock records a pid rather than merely existing. A presence-only lock would outlive a crash and leave the tray unstartable until someone found and deleted the file, which is worse than the failure it prevents. A dead or truncated pid reads as stale and is reclaimed.
- A recycled pid would read as alive and cost a refused launch rather than a duplicate icon. That is the safe direction to be wrong in, and it is why the check is `kill(pid, 0)` rather than something cleverer.
- Autostart is off until asked, and its state is read back from the platform rather than remembered. A recorded intention that drifted from the system is exactly the confusion doctor exists to end, so doctor must not consult the same memory that could be wrong.
- No `KeepAlive` in the LaunchAgent: quitting the tray from its own menu has to mean quit, not be restarted by launchd a second later.
- `cdx tray doctor` reads and never repairs. A doctor that also acted would have to be trusted with the machine; this one only has to be trusted to tell the truth, and a test asserts it creates nothing it reported as absent.
- A conflict in the corpus surfaced and was resolved rather than picked silently: req_035 AC3 forbids exposing accounts while the menu is closed, req_038 AC4 asks the tooltip to name the limiting source. A tooltip shows on hover with no click and appears in a screen share, so it carries the state, the figure and the reset in words, and never the session name. Both requests now say so.
- The tooltip is composed in CDX, not in each backend, so no platform can accidentally say more than the privacy rule allows and the accessibility wording is identical everywhere.
- A misconfigured WSL distribution is its own state, not a missing CDX. Reporting `CDX not found on this host` would be true of a distribution that does not exist and useless as a diagnosis, so the resolution is checked before the command runs and the installed distributions are listed.
- No fallback to the default when a configured name is unknown. Reading quota from a different distribution than the one configured is undiagnosable, and silence there is worse than an error.
- `wsl.exe -l` writes UTF-16LE. Decoded as UTF-8 the names arrive interleaved with NUL bytes, so a naive substring check passes for the wrong reason and fails for the right one. There is a test built from real output.
- Update ordering is the whole design: download, verify, prove it starts, then swap, then retire. A bad asset, a truncated download or a binary for the wrong architecture costs an error message rather than a tray the user can no longer start.
- Proving it starts is what separates staging from hoping. Without the probe, staging would only protect against a failed download, not against an asset that downloads perfectly and cannot execute here.
- A staged directory left behind is a recoverable state rather than corruption: doctor names it and the next install replaces it.
- The lock lives under the per-user temporary directory, not a shared path, so one user's companion cannot block another's on a shared machine.
- The smoke runner asks the companion for its lock path rather than recomputing the rule, which is TMPDIR here and LOCALAPPDATA on Windows. Every bug this session that a unit test missed came from a platform assumption restated in a second place, so `--lock-path` exists to stop the script becoming the next one.
- The runner names the companion's platform apart from the shell's, because driving a Windows companion from WSL is supported and a record reporting only `uname` would name the wrong tray under test.
- Poll cost is sampled three times, not once: the first sample pays for a cold WSL VM, and reporting only that would overstate the steady-state cost the 60s period has to afford.
- The Linux binary was cross-compiled static musl from macOS through rust-lld rather than installing a C toolchain in someone's WSL: the distribution has none, and `sudo` there wants a password that must never be handled from here. It also demonstrates the adr_005 property that the Linux asset carries no C library, since ksni and zbus are pure Rust.
- A check that cannot be exercised is skipped with its reason, never counted as a pass. Where no backend can draw, the first companion exits before a second can collide with it, so the single-instance check has nothing to ask; calling that a failure would cry wolf about the one host behaving correctly.
- Two AC3 clauses are blocked rather than quietly dropped. A toast reaching Action Center needs a notification to exist, which is `task_047`; a Zone.Identifier stream needs `cdx tray install` to fetch a release asset, which is `item_081`. Both are named in `item_085` with the slice that unblocks them.

# Links
- Request: `req_038_harden_cdx_tray_lifecycle_clarity_and_platform_validation`
- Product brief(s): `prod_027_trustworthy_cdx_tray_operation`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
