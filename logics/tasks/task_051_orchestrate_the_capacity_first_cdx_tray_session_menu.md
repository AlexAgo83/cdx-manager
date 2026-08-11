## task_051_orchestrate_the_capacity_first_cdx_tray_session_menu - Orchestrate the capacity-first CDX tray session menu
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Orchestrate the capacity-first CDX tray session menu
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Reproduce the interleaved-provider index mismatch from the current snapshot, menu model, runner row mapping, and macOS cell path.
- [ ] 2. Remove the provider grouping at the shared menu boundary and preserve stable session identity for labels, custom cells, and click actions.
- [ ] 3. Add compact provider text to the native fallback and macOS row layout without changing capacity, freshness, or reset information.
- [ ] 4. Add focused Rust regression coverage for capacity reordering and identity binding, then run the tray and project validation checks.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`. Proof deferred to slice closeout.
- request-AC2 -> `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`. Proof deferred to slice closeout.
- request-AC3 -> `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`. Proof deferred to slice closeout.
- request-AC4 -> `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`. Proof deferred to slice closeout.
- request-AC5 -> `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity`
- Product brief(s): `prod_029_capacity_first_cdx_tray_menu`
- Architecture decision(s): (none yet)
