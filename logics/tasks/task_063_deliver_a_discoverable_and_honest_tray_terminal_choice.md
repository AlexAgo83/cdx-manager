## task_063_deliver_a_discoverable_and_honest_tray_terminal_choice - Deliver a discoverable and honest tray terminal choice
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
- Summary: Deliver a discoverable terminal-candidate menu without turning preferences into arbitrary commands.
- Keywords: terminal candidate, native menu, Windows launcher, WSL transport
- Use when: Implementing the selectable terminal tray flow and its platform launch branches.
- Skip when: Changing the unrelated directory launch chooser.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Read src/tray_terminal.py, src/tray_contract.py, src/commands/tray.py and the three companion backends, and confirm the invariant that a preference names an application and never a command.
- [ ] 2. Declare the per-platform launchable catalogue in CDX, detect what is present, publish the candidates in the snapshot behind a minor schema bump, and add `cdx tray terminal list`.
- [ ] 3. Add the Windows launch branches for powershell, pwsh and cmd, then the contract test that keeps the catalogue and the companion branches in step.
- [ ] 4. Build the tray submenu from the candidates on all three backends, writing through CDX and repolling before the tick changes.
- [ ] 5. Run the Python suites, the Rust tray suite and lint, and document the preference and its Windows shell/application distinction in README.
- [ ] 6. Prove a candidate that disappears after snapshot creation never silently opens a different named terminal, and keep host versus WSL transport discovery explicit.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`
- `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`
- `item_103_offer_the_terminal_choice_as_a_tray_submenu`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC3 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof deferred to slice closeout.
- request-AC4 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof deferred to slice closeout.
- request-AC6 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof deferred to slice closeout.
- request-AC7 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof deferred to slice closeout.
- request-AC8 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof deferred to slice closeout.
- request-AC4 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof deferred to slice closeout.
- request-AC5 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof deferred to slice closeout.
- request-AC6 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof deferred to slice closeout.
- request-AC1 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof deferred to slice closeout.
- request-AC2 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof deferred to slice closeout.
- request-AC4 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof deferred to slice closeout.
- request-AC8 -> `item_103_offer_the_terminal_choice_as_a_tray_submenu`. Proof deferred to slice closeout.
- request-AC9 -> `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`. Proof deferred to slice closeout.
- request-AC10 -> `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
- Product brief(s): `prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest`
- Architecture decision(s): (none yet)
