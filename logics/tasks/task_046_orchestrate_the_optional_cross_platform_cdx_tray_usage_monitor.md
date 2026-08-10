## task_046_orchestrate_the_optional_cross_platform_cdx_tray_usage_monitor - Orchestrate the optional cross-platform CDX tray usage monitor
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 97%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-10 19:58:58
> Owner: claude

# AI Context
- Summary: Orchestrate the optional cross-platform CDX tray usage monitor
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- This task is the root of the tray chain. task_047 (alerts), task_048 (Logics card), and task_049 (lifecycle hardening) all consume the companion, the snapshot, and the WSL bridge built here, so none of them starts before this task is Done.
- task_049 is not an optional polish pass: no tray release ships without its single-instance, autostart, and doctor controls.
- adr_005 is settled and binds this chain: runtime, transport, refresh policy, poll budget, macOS signing identity, and per-user startup mechanisms. Revisit it through the ADR rather than diverging inside a slice.

# Plan
- [x] 1. Confirm the existing status JSON contract and define the smallest local tray command and display-state boundary without changing provider quota logic. The tray reads the existing session cache and never probes providers on a timer.
- [x] 1b. Stand up the build and signing capability before the first native slice: a Rust toolchain, the per-platform target matrix, and the self-signed macOS bundle step. Without it item_080 cannot be tested on macOS at all.
- [ ] 2. Build and validate the macOS and Windows host companions first, including the Windows-to-WSL status bridge and supplied icon assets.
- [ ] 3. Add the constrained Linux implementation and release-asset installer only after the companion boundary is proven on the two primary hosts.
- [ ] 4. Document the real trust model, installation through cdx tray install, CDX-managed updates, removal, platform support, and first-launch behaviour without overstating guarantees.
- [ ] 5. Run focused checks, platform smoke tests, project validation, Logics validation, lint, audit, and record the delivery context.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`
- `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`
- `item_081_add_linux_tray_support_and_explicit_release_asset_installation`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`. Proof deferred to slice closeout.
- request-AC2 -> `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`. Proof deferred to slice closeout.
- request-AC3 -> `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`. Proof deferred to slice closeout.
- request-AC4 -> `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`. Proof deferred to slice closeout.
- request-AC9 -> `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`. Proof deferred to slice closeout.
- request-AC10 -> `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`. Proof deferred to slice closeout.
- request-AC3 -> `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`. Proof deferred to slice closeout.
- request-AC4 -> `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`. Proof deferred to slice closeout.
- request-AC5 -> `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`. Proof deferred to slice closeout.
- request-AC6 -> `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`. Proof deferred to slice closeout.
- request-AC9 -> `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`. Proof deferred to slice closeout.
- request-AC10 -> `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`. Proof deferred to slice closeout.
- request-AC5 -> `item_081_add_linux_tray_support_and_explicit_release_asset_installation`. Proof deferred to slice closeout.
- request-AC7 -> `item_081_add_linux_tray_support_and_explicit_release_asset_installation`. Proof deferred to slice closeout.
- request-AC10 -> `item_081_add_linux_tray_support_and_explicit_release_asset_installation`. Proof deferred to slice closeout.
- request-AC8 -> `item_081_add_linux_tray_support_and_explicit_release_asset_installation`. Proof deferred to slice closeout.
- request-AC9 -> `item_081_add_linux_tray_support_and_explicit_release_asset_installation`. Proof deferred to slice closeout.

# Validation
- item_079 wave: `python3 -m pytest -q` 702 passed; `python3 -m ruff check src test` clean.
- macOS backend wave: `cargo test` 21 passed, `cargo clippy -- -D warnings` clean, `cargo fmt --check` clean; release binary 578 KB with the full tray stack; `cdx-tray --print` and `--help` behave; the companion launches, creates its status item, and stays alive on the arm64 macOS host without crashing. NOT YET VERIFIED: what the icon and menu actually look like in the menu bar. That needs a human.
- Menu and cadence wave: `cargo test` 18 passed, `cargo clippy -- -D warnings` clean, `cargo fmt --check` clean; the release binary renders the real menu against a live `cdx`, against a three-session snapshot covering auth-locked, fresh, and never-reported, and against a missing CDX.
- Build-capability wave: Rust 1.97.1 installed on the arm64 macOS host; `cargo test` 6 passed, `cargo clippy -- -D warnings` clean, `cargo fmt --check` clean; `./scripts/build-tray.sh` builds and assembles CDX.app and refuses to sign without an identity; four end-to-end runs of the release binary against a real `cdx` cover the happy path, an unknown snapshot major, a missing CDX, and a CDX too old to expose `cdx tray`.

# Report
- item_079 delivered. `src/tray_contract.py` derives the versioned snapshot, the icon state, and per-session freshness from the rows `cdx status` already returns. `src/commands/tray.py` adds `cdx tray status|install|launch|uninstall`; only `status` acts, the three companion actions are declared, non-mutating, and report `tray_companion_not_available`.
- The refresh policy is enforced in code, not only documented: `cdx tray status` calls `get_status_rows(cache_only=True, force_refresh=False)` and a test asserts it, so no future edit can quietly turn a tray poll into a provider probe.
- `auth_locked` is derived from a session being active rather than plumbed out of `codex_usage`, because the launcher holds the auth lock for the session's whole life. It is honest and needs no new plumbing; if a case appears where the lock is held without an active runtime, that derivation is the thing to revisit.
- Build capability delivered. `tray/` holds the `cdx-tray` crate, one dependency (`serde_json`), and `scripts/build-tray.sh` builds it, assembles `CDX.app` with `LSUIElement`, and signs it. The script refuses to sign ad-hoc and explains why, so the signing decision cannot be lost by someone in a hurry.
- The companion binary carries no tray UI yet, deliberately. It proves the transport instead: a separate process obtaining the snapshot, natively or across WSL, and refusing honestly when it cannot. That is the part item_080 would otherwise discover late.
- Found by running it: a CDX older than `cdx tray` is version drift in the direction the corpus had not covered, and it surfaced as a raw error envelope. The companion now reads the published `unknown_command` error code and says "update CDX". req_035 AC10 and item_080 gained the both-directions wording.
- Menu model and poll cadence delivered as pure logic, in `tray/src/menu.rs` and `tray/src/schedule.rs`, deliberately separate from the tray backend so both are testable without a windowing session. The adr_005 poll budget is enforced there rather than left to whoever writes the loop: 30s native, 60s across WSL, stop entirely with no enabled session, back off to 5 minutes after three consecutive failures.
- One decision worth recording: a failed read keeps the last known session count. Treating a transient error as "the user has no sessions" would stop polling for good on the first hiccup, exactly when something needs attention. There is a test for it.
- The menu spells out `auth_locked` as "running, cannot refresh" and leaves the Refresh entry visible but disabled. Hiding it would send the user hunting; enabling it would promise what the auth lock forbids.
- macOS backend wired. `tray/src/backend.rs` turns menu entries into muda items and picks the glyph; `tray/src/mac.rs` runs the loop. It pumps the NSApplication event queue itself with a 200 ms timeout rather than calling `app.run()`, because `run()` never returns and every tray mutation has to happen on the main thread. One loop, on the main thread: drain clicks, refresh when due, redraw.
- The glyphs are compiled into the binary with `include_bytes!`. The companion has to render an icon before it can report that anything is wrong, so a missing file on disk is not a failure mode worth having. Three tests assert they decode at 18px and are pure black on alpha, which is what makes the menu bar invert them per theme.
- Dependency cost measured rather than assumed: 96 transitive crates for tray-icon, muda, and the objc2 bindings, and a 578 KB release binary, up from 354 KB. objc2 rather than winit or tao, since the companion never opens a window.
- Remaining and it needs your eyes: whether the glyph and menu actually look right in the menu bar. The process starts, creates its status item and stays alive, but a terminal cannot judge a menu bar.
- Step order changed: item_079 ran before the build capability. It needed neither Rust nor a certificate, and it means the native slice will read a contract that is already written and tested rather than inventing both at once.

# Links
- Request: `req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor`
- Product brief(s): `prod_024_cdx_tray_usage_monitor`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
