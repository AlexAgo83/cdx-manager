## task_046_orchestrate_the_optional_cross_platform_cdx_tray_usage_monitor - Orchestrate the optional cross-platform CDX tray usage monitor
> From version: 0.17.1
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 93%
> Progress: 100%
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
- [x] 2. Build and validate the macOS and Windows host companions first, including the Windows-to-WSL status bridge and supplied icon assets.
- [x] 3. Add the constrained Linux implementation and release-asset installer only after the companion boundary is proven on the two primary hosts.
- [x] 4. Document the real trust model, installation through cdx tray install, CDX-managed updates, removal, platform support, and first-launch behaviour without overstating guarantees.
- [x] 5. Run focused checks, platform smoke tests, project validation, Logics validation, lint, audit, and record the delivery context.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`
- `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`
- `item_081_add_linux_tray_support_and_explicit_release_asset_installation`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `cdx tray` offers status, install, launch, uninstall, autostart, doctor, events, ack, heartbeat and alerts. Running `cdx` alone installs nothing, registers no startup and touches no desktop setting; a test asserts doctor creates nothing it reported absent.
- request-AC2 -> This task. Proof: the snapshot is read from the existing session cache with `cache_only`, which short-circuits the TTL entirely, so a poll never probes a provider. Verified in the field: eleven sessions on kdesktop all read `stale` rather than being passed off as fresh. `unavailable`, `stale`, `auth_locked` and never-reported are distinct states, and no figure is invented for any of them.
- request-AC3 -> This task. Proof: the closed icon carries a state, a reason and a count. The tooltip added later says the same in words and deliberately never a session name, since a tooltip appears on hover and in a screen share. Tested for all four states.
- request-AC4 -> This task. Proof: the menu lists every enabled session with provider, remaining figure, freshness or reset, plus refresh and a terminal action. Sorted most-constrained-first, because the store's order once put an account at 1% tenth while the icon showed critical.
- request-AC5 -> This task. Proof: the same contract drives all three backends. Linux capability is resolved at runtime through `org.kde.StatusNotifierWatcher`, never a distribution or desktop name — verified both ways on kdesktop's Ubuntu WSL: without a watcher the companion exits naming that, and against a minimal watcher it registers its item and keeps running.
- request-AC6 -> This task. Proof: the Windows companion reads CDX through `wsl.exe` interop with no X server, at 60 s. A misconfigured distribution is its own state, listing what is actually installed; a missing CDX says so. Both messages verified on the real host.
- request-AC7 -> This task. Proof: install picks the asset for this OS and architecture, verifies its published checksum before unpacking, records only what it wrote — including the Windows Start Menu shortcut — and needs no administrator rights. Exercised against the published release on macOS, Windows and Linux, ending with uninstall removing the companion and the shortcut and nothing else.
- request-AC8 -> This task. Proof: the README states the trust model as it is — the macOS bundle is self-signed, the published checksum is what vouches for it rather than Apple, installation goes through `cdx tray install` so no quarantine attribute or Mark of the Web is applied, and no browser download link is offered. It claims no Developer ID, no notarization, no store distribution, no background self-update, and no universal Linux support.
- request-AC9 -> This task. Proof: 782 Python tests and 45 Rust tests cover state mapping, JSON and staleness handling, target selection and checksum rejection, snapshot version drift, poll and backoff, and WSL command construction. `cargo clippy` is clean with zero warnings on three targets, and `scripts/tray-smoke.sh` passes on macOS, Windows-through-WSL and Linux.
- request-AC10 -> This task. Proof: measured rather than asserted — 374-382 ms per poll across WSL at 60 s, 140-145 ms natively at 30 s. Polling stops with no enabled session and backs off to 300 s after three failures. An unknown snapshot major keeps every field the reader understands and adds one hint; a CDX too old to know `cdx tray` produces "this CDX does not have `cdx tray`" rather than a raw error, verified against a real older CDX.

# Validation
- item_079 wave: `python3 -m pytest -q` 702 passed; `python3 -m ruff check src test` clean.
- macOS backend wave: `cargo test` 21 passed, `cargo clippy -- -D warnings` clean, `cargo fmt --check` clean; release binary 578 KB with the full tray stack; `cdx-tray --print` and `--help` behave; the companion launches, creates its status item, and stays alive on the arm64 macOS host without crashing. NOT YET VERIFIED: what the icon and menu actually look like in the menu bar. That needs a human.
- Menu and cadence wave: `cargo test` 18 passed, `cargo clippy -- -D warnings` clean, `cargo fmt --check` clean; the release binary renders the real menu against a live `cdx`, against a three-session snapshot covering auth-locked, fresh, and never-reported, and against a missing CDX.
- Build-capability wave: Rust 1.97.1 installed on the arm64 macOS host; `cargo test` 6 passed, `cargo clippy -- -D warnings` clean, `cargo fmt --check` clean; `./scripts/build-tray.sh` builds and assembles CDX.app and refuses to sign without an identity; four end-to-end runs of the release binary against a real `cdx` cover the happy path, an unknown snapshot major, a missing CDX, and a CDX too old to expose `cdx tray`.
- 2026-08-11: npm test 782 passed, cargo test 45 passed, cargo clippy zero warnings on three targets, npm run lint clean, tray-smoke 6/6 on macOS arm64 and Windows-through-WSL. cdx tray install verified against the published v0.18.2 release on macOS, Windows and Linux. Linux watcher path verified both ways on kdesktop's Ubuntu WSL.
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

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
- Finished on 2026-08-11.
- Linked backlog item(s): `item_079_define_the_minimal_tray_status_contract_and_cdx_command_surface`, `item_080_build_native_tray_companions_for_macos_and_windows_plus_wsl`, `item_081_add_linux_tray_support_and_explicit_release_asset_installation`
- Related request(s): `req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor`

# Links
- Request: `req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor`
- Product brief(s): `prod_024_cdx_tray_usage_monitor`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
