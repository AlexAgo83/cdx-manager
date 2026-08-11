## task_051_orchestrate_the_capacity_first_cdx_tray_session_menu - Orchestrate the capacity-first CDX tray session menu
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 92%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

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
- [x] 1. Reproduce the interleaved-provider index mismatch across the snapshot, the two numbering schemes in the menu model, the runner row mapping, and the macOS cell path.
- [x] 2. Remove the provider grouping at the shared menu boundary and replace the positional `ActionId::Session(index)` with a stable session identifier used by labels, custom cells, and click actions.
- [x] 3. Add compact provider text to the native fallback and macOS row layout without changing capacity, freshness, or reset information.
- [x] 4. Add focused Rust regression coverage for capacity reordering and identity binding, including a snapshot that reorders between the draw and the click, then run the tray and project validation checks.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `grouped()` is gone from `tray/src/menu.rs`; sessions are appended straight from `snapshot.sessions`. Covered by `sessions_are_listed_once_each_in_snapshot_order`, which asserts the clicked ids come back in snapshot order and no heading line survives (3e0c96d).
- request-AC2 -> This task. Proof: `session_line` renders `name · provider`, and `Row`/`mac_cell::Cell` carry `provider` so the drawn macOS row states it too — a view-bearing NSMenuItem draws no label of its own. Asserted in `every_session_gets_a_line_with_its_figure_and_its_trust` (3e0c96d).
- request-AC3 -> This task. Proof: `ActionId::Session` carries the session name instead of a snapshot rank, and `rows_for` resolves cells by name. `a_session_overtaking_another_still_opens_the_row_that_was_clicked` reorders a Codex session past two Claude ones and asserts every id stays bound to its own row (3e0c96d).
- request-AC4 -> This task. Proof: the gauge, figure, freshness, reset, alert history, refresh-disabled and no-session paths are unchanged; their existing tests pass untouched — 54 tray tests green, the only edited assertions being the two that named the old grouped layout (3e0c96d).
- request-AC5 -> This task. Proof: `cargo test` (54 passed), `cargo fmt --check`, `cargo clippy --all-targets`, and `cargo check` on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu, since two of the three backends do not compile on the dev host (3e0c96d).

# Validation
- (no validation recorded yet)
- command: `cargo test && cargo fmt --check && cargo clippy --all-targets && cargo check --target x86_64-pc-windows-msvc && cargo check --target x86_64-unknown-linux-gnu` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`
- Related request(s): `req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity`

# Links
- Request: `req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity`
- Product brief(s): `prod_029_capacity_first_cdx_tray_menu`
- Architecture decision(s): (none yet)
