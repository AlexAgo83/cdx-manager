## task_069_orchestrate_repository_grouped_logics_tray_navigation - Orchestrate repository-grouped Logics tray navigation
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: Codex

# AI Context
- Summary: Render a bounded, compatible repository hierarchy for Logics next actions in the tray.
- Keywords: repository label, submenu, card schema, collision
- Use when: Implementing repository-grouped Logics tray navigation.
- Skip when: Changing non-Logics session or alert menu groups.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace the current multi-root Logics adapter output through Python card validation, snapshot parsing, native menu construction, and focused viewer action dispatch.
- [x] 2. Design the smallest optional bounded repository-group field that preserves legacy flat-card compatibility and stable roots.
- [x] 3. Publish groups per root and render native repository submenus with their blocked and next actions, retaining card-wide actions.
- [x] 4. Exercise source-companion rendering and focused actions against multiple repository roots, then record Python, Rust, and Logics validation evidence before closeout.
- [x] 5. Add collision-safe repository labels, a five-group/two-row bound, and an explicit snapshot minor-version compatibility test before the native smoke test.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`
- `item_116_render_logics_repository_groups_as_native_tray_submenus`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: `d62989b`; Python multi-root group test passed.
- request-AC2 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: `d62989b`; Python group-row test passed.
- request-AC3 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: `d62989b`; root is preserved in each `logics.focus` row.
- request-AC4 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: `d62989b`; five-group/two-row bounds are covered by tests.
- request-AC5 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: `d62989b`; Rust parser drops malformed groups and keeps flat rows.
- request-AC6 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: Python and Rust tray suites passed on 2026-08-13.
- request-AC1 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: `d62989b`; Rust menu submenu test passed.
- request-AC2 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: `d62989b`; submenu child labels come from repository rows.
- request-AC3 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: `d62989b`; `ActionId::Logics` retains the structured root.
- request-AC4 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: `d62989b`; card-wide actions remain outside group menus.
- request-AC5 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: `d62989b`; legacy flat-card Rust test passed.
- request-AC6 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: Rust suite passed (91 tests) on 2026-08-13.
- request-AC7 -> `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`. Proof: `d62989b`; collision-safe labels test passed without using labels as targets.
- request-AC8 -> `item_116_render_logics_repository_groups_as_native_tray_submenus`. Proof: `d62989b`; parser and menu bounds are covered by Rust tests.

# Validation
- (no validation recorded yet)
- command: `node bin/python-runner.js -m unittest discover -s test -p 'test_tray_plugins_py.py' && cargo test --manifest-path tray/Cargo.toml && npm run lint && logics-manager lint --require-status && logics-manager audit --group-by-doc` | result: passed | date: 2026-08-13
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`, `item_116_render_logics_repository_groups_as_native_tray_submenus`
- Related request(s): `req_058_group_logics_tray_next_actions_by_repository`

# Links
- Request: `req_058_group_logics_tray_next_actions_by_repository`
- Product brief(s): `prod_045_repository_oriented_logics_tray_navigation`
- Architecture decision(s): (none yet)
