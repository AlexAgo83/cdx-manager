## task_058_orchestrate_the_preferred_tray_terminal - Orchestrate the preferred tray terminal
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, preferred, tray, terminal
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. 1. Trace how each backend opens a terminal today and what the snapshot already carries.
- [x] 2. 2. Define the smallest validated preference that cannot express a command, and the CDX surface to set, show and clear it.
- [x] 3. 3. Carry it through the snapshot and honour it per platform, with a fallback to today's behaviour.
- [x] 4. 4. Add focused tests for each outcome and document what the setting cannot do.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `cdx tray terminal set <app>`, `status` and `clear` in `src/commands/tray.py`, backed by `src/tray_terminal.py`. Covered by `test_an_application_name_is_stored_and_reversible` (147e702).
- request-AC2 -> This task. Proof: `build_snapshot` carries `terminal`, the companion reads it into `Snapshot.terminal`, and no store exists on the companion side. Covered by `test_the_snapshot_carries_it` and `the_chosen_terminal_arrives_with_the_snapshot` (147e702).
- request-AC3 -> This task. Proof: macOS falls back to Terminal.app when `open -a` fails, Linux continues down its existing list after a failed spawn, and Windows falls back to the console it always opened. A click that opens the wrong terminal beats a click that opens nothing (147e702).
- request-AC4 -> This task. Proof: the value must match an application name — no slashes, quotes, semicolons, ampersands, pipes, backticks or dollars, and no leading flag — and it is validated on read as well as on write, so a state file edited by anything else is not honoured. Covered by `test_anything_that_could_be_a_command_is_refused` and `test_a_stored_value_that_no_longer_validates_is_not_honoured` (147e702).
- request-AC5 -> This task. Proof: `open -a` on macOS with a one-shot script for terminals that have no scripting dialect, the named emulator ahead of the existing list on Linux, and `wt -- <command>` on Windows — the only terminal there that documents how to be handed a command. All three are documented in the README, including why Windows honours one name (147e702).
- request-AC6 -> This task. Proof: 861 Python tests and 88 tray tests pass; ruff, cargo fmt --check and cargo clippy --all-targets clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu. Default, named, absent and refused values are each covered (147e702).

# Validation
- (no validation recorded yet)
- command: `python3 -m pytest (861 passed), ruff, cargo test (88 passed), cargo fmt --check, cargo clippy on the three targets` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`
- Related request(s): `req_047_let_the_operator_choose_which_terminal_the_tray_opens`

# Links
- Request: `req_047_let_the_operator_choose_which_terminal_the_tray_opens`
- Product brief(s): `prod_034_the_tray_opens_the_terminal_you_actually_use`
- Architecture decision(s): (none yet)
