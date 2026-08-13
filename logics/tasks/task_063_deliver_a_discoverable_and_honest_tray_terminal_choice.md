## task_063_deliver_a_discoverable_and_honest_tray_terminal_choice - Deliver a discoverable and honest tray terminal choice
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
- Summary: Deliver a discoverable terminal-candidate menu without turning preferences into arbitrary commands.
- Keywords: terminal candidate, native menu, Windows launcher, WSL transport
- Use when: Implementing the selectable terminal tray flow and its platform launch branches.
- Skip when: Changing the unrelated directory launch chooser.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Read src/tray_terminal.py, src/tray_contract.py, src/commands/tray.py and the three companion backends, and confirm the invariant that a preference names an application and never a command.
- [x] 2. Declare the per-platform launchable catalogue in CDX, detect what is present, publish the candidates in the snapshot behind a minor schema bump, and add `cdx tray terminal list`.
- [x] 3. Add the Windows launch branches for powershell, pwsh and cmd, then the contract test that keeps the catalogue and the companion branches in step.
- [x] 4. Build the tray submenu from the candidates on all three backends, writing through CDX and repolling before the tick changes.
- [x] 5. Run the Python suites, the Rust tray suite and lint, and document the preference and its Windows shell/application distinction in README.
- [x] 6. Prove a candidate that disappears after snapshot creation never silently opens a different named terminal, and keep host versus WSL transport discovery explicit.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`
- `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`
- `item_103_offer_the_terminal_choice_as_a_tray_submenu`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC3 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof: `cdx tray terminal list --json` passed on macOS and Tower Windows.
- request-AC4 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof: macOS reported only Terminal/iTerm; Tower reported wt/powershell/cmd.
- request-AC6 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof: snapshot parser and 40 Python tests passed.
- request-AC7 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof: invalid command-shaped preferences remain rejected.
- request-AC8 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof: older WSL v1.2 snapshot was consumed by the v1.3 companion.
- request-AC4 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof: Tower native candidate catalogue and preference write/read passed.
- request-AC5 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof: native and WSL transport branches compiled and passed 90 Rust tests on Tower.
- request-AC6 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof: declared candidates and companion branches are covered by Tower smoke tests.
- request-AC1 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof: macOS live menu test passed with System default, Terminal and iTerm.
- request-AC2 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof: Tower set powershell then clear passed through CDX.
- request-AC4 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof: macOS and Tower native trays rendered from their platform snapshots.
- request-AC8 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof: old WSL snapshot without candidates stayed compatible.
- request-AC9 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof: `756ff0a` prevents named-terminal fallback.
- request-AC10 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof: Tower native and WSL smoke tests passed separately on 2026-08-13.

# Validation
- (no validation recorded yet)
- command: `macOS and Tower Windows/WSL smoke: terminal list, set/clear; 40 Python tests; 92 macOS Rust tests; 90 Tower Rust tests; npm run lint; Logics lint/audit` | result: passed | date: 2026-08-13
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`, `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`, `item_103_offer_the_terminal_choice_as_a_tray_submenu`
- Related request(s): `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`

# Links
- Request: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
- Product brief(s): `prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest`
- Architecture decision(s): (none yet)
