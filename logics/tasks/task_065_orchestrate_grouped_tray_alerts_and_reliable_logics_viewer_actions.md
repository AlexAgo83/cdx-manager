## task_065_orchestrate_grouped_tray_alerts_and_reliable_logics_viewer_actions - Orchestrate grouped tray alerts and reliable Logics viewer actions
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-13 00:53:55
> Owner: Codex

# AI Context
- Summary: Deliver the two linked recovery paths in order: menu-only alert grouping, then detached repository-aware Logics viewer launches proven through the installed macOS tray.
- Keywords: orchestrate, grouped, tray, alerts, reliable, logics, viewer, actions
- Use when: Executing the request chain after the Logics Fleet viewer release is available.
- Skip when: The work is only a visual tray redesign or a Logics server implementation.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace the event-to-menu and plugin-card-to-action paths on macOS, then pin the current flat grouping and blocking/inert viewer failures with focused checks.
- [x] 2. Implement the smallest menu-only alert grouping over the existing unread list, preserving its consultation boundary and stable action identity.
- [x] 3. Extend the bounded first-party Logics row context and implement detached global Fleet and focused project viewer launches using the upcoming supported Logics CLI contract.
- [x] 4. Exercise the installed macOS companion against real session alerts and both Logics actions; verify the browser opens, focused navigation targets the originating repository, and the tray remains responsive.
- [x] 5. Record implementation evidence, update concise documentation if the user-visible behaviour changes, and run project plus Logics validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_107_group_unread_tray_alerts_by_their_originating_session`
- `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Session alert submenus with counts are covered by Rust menu tests. Source: `82f16d9`
- request-AC2 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Events without session remain a non-actionable Other alerts group. Source: `82f16d9`
- request-AC3 -> This task. Proof: date: 2026-08-13 | command: `npm test && cargo test --manifest-path tray/Cargo.toml` | result: passed | Existing unread, notification, acknowledgement, and mute coverage remains green. Source: `82f16d9`
- request-AC4 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Structured alert actions retain stable session identities in nested groups. Source: `82f16d9`
- request-AC8 -> This task. Proof: date: 2026-08-13 | command: `npm test && cargo test --manifest-path tray/Cargo.toml && cargo clippy --manifest-path tray/Cargo.toml --all-targets -- -D warnings && npm run lint` | result: passed | Full Python and Rust suite, Clippy, lint, and macOS source smoke passed. Source: `82f16d9`
- request-AC5 -> This task. Proof: date: 2026-08-13 | command: `node bin/cdx.js tray plugin run logics.open --json` | result: passed | Global action launches detached Fleet viewer with --open; macOS source smoke passed. Source: `82f16d9`
- request-AC6 -> This task. Proof: date: 2026-08-13 | command: `node bin/cdx.js tray plugin run logics.focus:task_065_orchestrate_grouped_tray_alerts_and_reliable_logics_viewer_actions --root /Users/alexandreagostini/Documents/cdx-manager --json` | result: passed | Focused action launches detached project viewer with root cwd and --open; macOS source smoke passed. Source: `82f16d9`
- request-AC7 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- test/test_tray_plugins_py.py` | result: passed | Root context is bounded, unrendered, and revalidated before launch. Source: `82f16d9`
- request-AC8 -> This task. Proof: date: 2026-08-13 | command: `npm test && cargo test --manifest-path tray/Cargo.toml && cargo clippy --manifest-path tray/Cargo.toml --all-targets -- -D warnings && npm run lint` | result: passed | Full Python and Rust suite, Clippy, lint, and macOS source smoke passed. Source: `82f16d9`

# Validation
- (no validation recorded yet)
- command: `npm test && cargo test --manifest-path tray/Cargo.toml && cargo clippy --manifest-path tray/Cargo.toml --all-targets -- -D warnings && npm run lint` | result: passed | date: 2026-08-13 | note: macOS source smoke passed: native companion rendered the real snapshot and global/focused Logics viewer actions returned immediately.
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_107_group_unread_tray_alerts_by_their_originating_session`, `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`
- Related request(s): `req_054_group_tray_alerts_by_session_and_make_logics_actions_reliably_open_the_viewer`

# Links
- Request: `req_054_group_tray_alerts_by_session_and_make_logics_actions_reliably_open_the_viewer`
- Product brief(s): `prod_041_contextual_cdx_tray_recovery_paths`
- Architecture decision(s): (none yet)

# Evidence
- AC1 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Session alert submenus with counts are covered by Rust menu tests.
- AC2 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Events without session remain a non-actionable Other alerts group.
- AC3 | date: 2026-08-13 | command: `npm test && cargo test --manifest-path tray/Cargo.toml` | result: passed | Existing unread, notification, acknowledgement, and mute coverage remains green.
- AC4 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Structured alert actions retain stable session identities in nested groups.
- AC5 | date: 2026-08-13 | command: `node bin/cdx.js tray plugin run logics.open --json` | result: passed | Global action launches detached Fleet viewer with --open; macOS source smoke passed.
- AC6 | date: 2026-08-13 | command: `node bin/cdx.js tray plugin run logics.focus:task_065_orchestrate_grouped_tray_alerts_and_reliable_logics_viewer_actions --root /Users/alexandreagostini/Documents/cdx-manager --json` | result: passed | Focused action launches detached project viewer with root cwd and --open; macOS source smoke passed.
- AC7 | date: 2026-08-13 | command: `npm run test:py -- test/test_tray_plugins_py.py` | result: passed | Root context is bounded, unrendered, and revalidated before launch.
- AC8 | date: 2026-08-13 | command: `npm test && cargo test --manifest-path tray/Cargo.toml && cargo clippy --manifest-path tray/Cargo.toml --all-targets -- -D warnings && npm run lint` | result: passed | Full Python and Rust suite, Clippy, lint, and macOS source smoke passed.
