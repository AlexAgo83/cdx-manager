## task_069_orchestrate_repository_grouped_logics_tray_navigation - Orchestrate repository-grouped Logics tray navigation
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 90%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Render a bounded, compatible repository hierarchy for Logics next actions in the tray.
- Keywords: repository label, submenu, card schema, collision
- Use when: Implementing repository-grouped Logics tray navigation.
- Skip when: Changing non-Logics session or alert menu groups.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace the current multi-root Logics adapter output through Python card validation, snapshot parsing, native menu construction, and focused viewer action dispatch.
- [ ] 2. Design the smallest optional bounded repository-group field that preserves legacy flat-card compatibility and stable roots.
- [ ] 3. Publish groups per root and render native repository submenus with their blocked and next actions, retaining card-wide actions.
- [ ] 4. Exercise source-companion rendering and focused actions against multiple repository roots, then record Python, Rust, and Logics validation evidence before closeout.
- [ ] 5. Add collision-safe repository labels, a five-group/two-row bound, and an explicit snapshot minor-version compatibility test before the native smoke test.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`
- `item_116_render_logics_repository_groups_as_native_tray_submenus`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC2 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC3 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC4 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC5 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC6 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC1 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.
- request-AC2 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.
- request-AC3 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.
- request-AC4 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.
- request-AC5 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.
- request-AC6 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.
- request-AC7 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof deferred to slice closeout.
- request-AC8 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_058_group_logics_tray_next_actions_by_repository`
- Product brief(s): `prod_045_repository_oriented_logics_tray_navigation`
- Architecture decision(s): (none yet)
