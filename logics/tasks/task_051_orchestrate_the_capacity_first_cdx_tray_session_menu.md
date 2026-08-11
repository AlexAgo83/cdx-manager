## task_051_orchestrate_the_capacity_first_cdx_tray_session_menu - Orchestrate the capacity-first CDX tray session menu
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 92%
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
- The mismatch is two numbering schemes over one list. `menu.rs:134-179` inserts an `Entry::Info(provider)` per group but advances `index` only on sessions, while the drawn cell receives `row.menu_index`, a position in the menu that counts the headings.
- Flattening removes the headings, so the two schemes converge on their own. No separate index fix is needed once the grouping is gone.
- The residual defect is different and survives flattening: `ActionId::Session(index)` (`menu.rs:37`) is a rank in the snapshot, and this task makes that rank depend on capacity. A snapshot that changes between the draw and the click then opens the wrong session. Session identity has to become an identifier, at the cost of ActionId no longer being `Copy`.
- `menu.rs:116` records that the provider was taken off the row because the heading carried it. This task reverses that decision, so the comment goes with it.
- Do this before task_054: that task binds per-row actions to the same identity, and doing it after would bind them to a rank this task has just made volatile.

# Plan
- [ ] 1. Reproduce the interleaved-provider index mismatch across the snapshot, the two numbering schemes in the menu model, the runner row mapping, and the macOS cell path.
- [ ] 2. Remove the provider grouping at the shared menu boundary and replace the positional `ActionId::Session(index)` with a stable session identifier used by labels, custom cells, and click actions.
- [ ] 3. Add compact provider text to the native fallback and macOS row layout without changing capacity, freshness, or reset information.
- [ ] 4. Add focused Rust regression coverage for capacity reordering and identity binding, including a snapshot that reorders between the draw and the click, then run the tray and project validation checks.
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
