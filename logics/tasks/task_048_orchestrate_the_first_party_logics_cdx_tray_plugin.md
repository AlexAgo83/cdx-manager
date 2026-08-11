## task_048_orchestrate_the_first_party_logics_cdx_tray_plugin - Orchestrate the first-party Logics CDX tray plugin
> From version: 0.17.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-10 13:29:56
> Owner: corvus

# AI Context
- Summary: Orchestrate the first-party Logics CDX tray plugin
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Blocked on task_046: the card is delivered through the base tray snapshot and menu. Do not start it while task_046 is open.
- The card rides the existing snapshot refresh from adr_005 and adds no polling loop or interop call of its own.

# Plan
- [x] 1. Confirm the base tray snapshot boundary and implement the fixed v1 Logics menu: blocked/ready summary, at most two ordered rows, global Open Logics action, and focused row actions.
- [x] 2. Define the smallest versioned CDX-owned plugin-card schema and registry, including strict bounds, fixed timeout, availability, and action-id validation.
- [x] 3. Implement the Logics adapter from status JSON only, then wire explicit enable, disable, status, refresh, and focused-view routes through CDX.
- [x] 4. Pass the card to the existing tray menu and verify native plus WSL environment selection without adding tray-side plugin execution or polling.
- [x] 5. Add focused checks, document the first-party adapter and deferred marketplace decision, then run project and workflow validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `build_snapshot` carries a `plugins` array at schema minor 1, and `bounded_card` validates every card. Malformed, unknown, throwing, timing-out and absent adapters all yield nothing — `test_an_adapter_that_throws_costs_only_its_own_card`, `test_an_adapter_returning_nonsense_produces_no_card`, `test_a_timeout_is_silence` (b9f21e6).
- request-AC2 -> This task. Proof: nothing is enabled by default (`test_nothing_is_enabled_by_default`), the adapter reads only `logics-manager status --format json`, and every failure path returns None rather than a card (b9f21e6).
- request-AC3 -> This task. Proof: the card is one summary plus at most two rows — the first blocked document and the highest-priority active task — asserted by `test_the_two_rows_are_what_stops_work_and_what_to_do_instead`, and the bound is re-checked in the companion by `a_card_cannot_contribute_more_than_two_rows` (b9f21e6, 0d34950).
- request-AC4 -> This task. Proof: action ids are matched against a fixed vocabulary in `tray_plugin_actions.perform_action`; anything else is refused, including ids that would be shell metacharacters (`test_an_action_that_could_be_a_command_is_dropped`, `test_an_unknown_action_is_refused`) (b9f21e6).
- request-AC5 -> This task. Proof: cards ride the existing snapshot with no tray-side loop, and the card is reused for `CARD_TTL_SECONDS` while a manual refresh passes no cache — `test_a_card_is_reused_within_its_ttl_and_re_asked_after` and `test_a_manual_refresh_passes_no_cache_and_so_re_asks` (b9f21e6).
- request-AC6 -> This task. Proof: the adapter resolves `logics-manager` through CDX's own lookup and runs it as CDX, never as a path the companion knows — `test_the_command_is_resolved_through_cdx_not_by_the_tray`. The companion only ever sends `cdx tray plugin run <id>` back over the existing transport (b9f21e6, 0d34950).
- request-AC7 -> This task. Proof: `cdx tray plugin enable|disable|status` is explicit and reversible (`test_enabling_is_reversible`), an unknown name is refused, and an installed but disabled Logics manager is reported once as activatable rather than enabled implicitly (b9f21e6).
- request-AC8 -> This task. Proof: README documents activation, what a card is built from, the privacy boundary, failure semantics and the deliberately absent marketplace. 850 Python tests and 75 tray tests pass; ruff, cargo fmt and clippy clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu (0d34950).

# Validation
- (no validation recorded yet)
- command: `python3 -m pytest (850 passed), ruff, cargo test (75 passed), cargo fmt --check, cargo clippy --all-targets on the macOS/Windows/Linux targets` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`
- Related request(s): `req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray`

# Links
- Request: `req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray`
- Product brief(s): `prod_026_extensible_cdx_tray_with_a_first_party_logics_card`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
