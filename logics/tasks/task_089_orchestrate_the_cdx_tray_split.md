## task_089_orchestrate_the_cdx_tray_split - Orchestrate the cdx-tray split
> From version: 0.27.12
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, cdx, tray, split
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Contract first (item 1), released in a cdx version so cdx-tray can rely on it.
- [ ] 2. Create cdx-tray (item 2) and publish its first release built from the same sources.
- [ ] 3. Switch `cdx tray install` (item 3), then remove the tray from cdx-manager (item 4) in the next cdx release.
- [ ] 4. Verify on a real machine: install, launch, menu refresh, and a cdx release that publishes without tray jobs.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_172_version_the_tray_contract_and_pin_its_json_shape`
- `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`
- `item_174_install_the_tray_from_cdx_tray_releases`
- `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_172_version_the_tray_contract_and_pin_its_json_shape`. Proof deferred to slice closeout.
- request-AC2 -> `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`. Proof deferred to slice closeout.
- request-AC5 -> `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`. Proof deferred to slice closeout.
- request-AC3 -> `item_174_install_the_tray_from_cdx_tray_releases`. Proof deferred to slice closeout.
- request-AC4 -> `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`
- Product brief(s): `prod_059_cdx_tray_the_tray_companion_released_on_its_own`
- Architecture decision(s): (none yet)

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

