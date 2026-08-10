## task_048_orchestrate_the_first_party_logics_cdx_tray_plugin - Orchestrate the first-party Logics CDX tray plugin
> From version: 0.17.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-10 13:29:56

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
- [ ] 1. Confirm the base tray snapshot boundary and implement the fixed v1 Logics menu: blocked/ready summary, at most two ordered rows, global Open Logics action, and focused row actions.
- [ ] 2. Define the smallest versioned CDX-owned plugin-card schema and registry, including strict bounds, fixed timeout, availability, and action-id validation.
- [ ] 3. Implement the Logics adapter from status JSON only, then wire explicit enable, disable, status, refresh, and focused-view routes through CDX.
- [ ] 4. Pass the card to the existing tray menu and verify native plus WSL environment selection without adding tray-side plugin execution or polling.
- [ ] 5. Add focused checks, document the first-party adapter and deferred marketplace decision, then run project and workflow validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC2 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC3 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC4 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC5 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC6 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC7 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.
- request-AC8 -> `item_083_add_the_cdx_tray_plugin_contract_and_built_in_logics_status_card`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_037_add_a_first_party_logics_plugin_surface_to_the_cdx_tray`
- Product brief(s): `prod_026_extensible_cdx_tray_with_a_first_party_logics_card`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
