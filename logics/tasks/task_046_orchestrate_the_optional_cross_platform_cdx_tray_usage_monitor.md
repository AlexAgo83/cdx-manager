## task_046_orchestrate_the_optional_cross_platform_cdx_tray_usage_monitor - Orchestrate the optional cross-platform CDX tray usage monitor
> From version: 0.17.1
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 25%
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
- [ ] 1b. Stand up the build and signing capability before the first native slice: a Rust toolchain, the per-platform target matrix, and the self-signed macOS bundle step. Without it item_080 cannot be tested on macOS at all.
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

# Report
- item_079 delivered. `src/tray_contract.py` derives the versioned snapshot, the icon state, and per-session freshness from the rows `cdx status` already returns. `src/commands/tray.py` adds `cdx tray status|install|launch|uninstall`; only `status` acts, the three companion actions are declared, non-mutating, and report `tray_companion_not_available`.
- The refresh policy is enforced in code, not only documented: `cdx tray status` calls `get_status_rows(cache_only=True, force_refresh=False)` and a test asserts it, so no future edit can quietly turn a tray poll into a provider probe.
- `auth_locked` is derived from a session being active rather than plumbed out of `codex_usage`, because the launcher holds the auth lock for the session's whole life. It is honest and needs no new plumbing; if a case appears where the lock is held without an active runtime, that derivation is the thing to revisit.
- Step order changed: item_079 ran before the build capability. It needed neither Rust nor a certificate, and it means the native slice will read a contract that is already written and tested rather than inventing both at once.

# Links
- Request: `req_035_add_an_optional_cross_platform_cdx_tray_usage_monitor`
- Product brief(s): `prod_024_cdx_tray_usage_monitor`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
