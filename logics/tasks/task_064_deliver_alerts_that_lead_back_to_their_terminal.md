## task_064_deliver_alerts_that_lead_back_to_their_terminal - Deliver alerts that lead back to their terminal
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
- Summary: Carry safe terminal-origin metadata from an alert to an honest native focus action.
- Keywords: alert origin, terminal identity, stale alert, macOS notification
- Use when: Implementing alert focus behavior or notification click parity.
- Skip when: Changing alert delivery volume or mute preferences.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Confirm on the development host what a hook can observe: no tty on any descriptor, and which terminal variables survive into it.
- [x] 2. Extend structured_details with the terminal identity, arguing the addition in the module's own terms, and publish it in the alert.
- [x] 3. Add the focus action to alert rows, implement the macOS iTerm2 path, and render unavailability with its reason everywhere else.
- [x] 4. Probe Terminal.app and record the finding, supported or not, rather than leaving it open.
- [x] 5. Add the macOS notification delegate so a banner click resolves through the same path as the row.
- [x] 6. Run the Python suites, the Rust tray suite and the tray smoke script, and document the behaviour and its authorization prompt.
- [x] 7. Treat terminal identity as untrusted structured metadata: validate it at receipt and click time, and prove stale retained alerts cannot fall back to a different window.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`
- `item_105_focus_the_originating_terminal_from_a_tray_alert_row`
- `item_106_make_the_notification_banner_act_like_the_alert_row_on_macos`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | Hook captures only inherited iTerm identity or no identity. Source: `7308440`
- request-AC6 -> This task. Proof: date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | Terminal identity is allowlisted and bounded before the tray receives it. Source: `7308440`
- request-AC7 -> This task. Proof: date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | Structured alert metadata documents and preserves the privacy boundary. Source: `7308440`
- request-AC2 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Menu focus uses the exact validated iTerm session id. Source: `7308440`
- request-AC3 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Stale and malformed terminal ids cannot select another window. Source: `7308440`
- request-AC4 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Unsupported focus states are rendered unavailable instead of guessed. Source: `7308440`
- request-AC5 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Native macOS banner clicks resolve through the shared focus path. Source: `7308440`
- request-AC8 -> This task. Proof: date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | No transcript or tool input is used to derive terminal metadata. Source: `7308440`
- request-AC9 -> This task. Proof: date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Retained alerts revalidate their opaque terminal target on click. Source: `7308440`

# Validation
- (no validation recorded yet)
- 2026-08-13: cargo test --manifest-path tray/Cargo.toml (96 passed); node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py (37 passed); npm run lint (passed); scripts/tray-dev.sh load (passed).
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`, `item_105_focus_the_originating_terminal_from_a_tray_alert_row`, `item_106_make_the_notification_banner_act_like_the_alert_row_on_macos`
- Related request(s): `req_053_bring_back_the_terminal_an_alert_came_from`

# Links
- Request: `req_053_bring_back_the_terminal_an_alert_came_from`
- Product brief(s): `prod_040_alerts_that_lead_back_to_their_terminal`
- Architecture decision(s): (none yet)

# Evidence
- AC1 | date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | Hook captures only inherited iTerm identity or no identity.
- AC2 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Menu focus uses the exact validated iTerm session id.
- AC3 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Stale and malformed terminal ids cannot select another window.
- AC4 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Unsupported focus states are rendered unavailable instead of guessed.
- AC5 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Native macOS banner clicks resolve through the shared focus path.
- AC6 | date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | Terminal identity is allowlisted and bounded before the tray receives it.
- AC7 | date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | Structured alert metadata documents and preserves the privacy boundary.
- AC8 | date: 2026-08-13 | command: `node bin/python-runner.js -m unittest discover -s test -p test_agent_notify_py.py` | result: passed | No transcript or tool input is used to derive terminal metadata.
- AC9 | date: 2026-08-13 | command: `cargo test --manifest-path tray/Cargo.toml` | result: passed | Retained alerts revalidate their opaque terminal target on click.
