## task_061_orchestrate_commands_that_name_what_they_touch - Orchestrate commands that name what they touch
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:40:12

# AI Context
- Summary: Two slices: install-side prefix reporting, and doctor reporting what the companion and the hooks actually reach.
- Keywords: diagnostics, HOME redirection, tray doctor, run_002
- Use when: Implementing req_050. run_002 is the manual diagnosis this replaces, and lists the four questions to answer.
- Skip when: Repairing a mismatch automatically, or changing resolution rules.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- The evidence is three incidents in one day, all the same shape: `cdx update` run inside a session installed into that session's profile and reported plain success while the operator's own installation stayed behind; a hook published into a store no companion was watching, so an alert was delivered directly while a tray was plainly running; and a companion crossing into WSL resolved an older `cdx` through a non-login PATH and told the operator to update something already current.
- None of them is a bug in what the code does. The installer installs where `HOME` points, the hook writes where `CDX_HOME` points, and the companion runs what `PATH` resolves. Each is correct and none of them says which one it picked.
- `run_002` is the manual diagnosis this replaces, and it lists the four questions in the order that answers fastest. The point of the task is to make the tool answer them itself.
- Where each fact already exists: the install prefix in `_build_standalone_step` (`src/update_manager.py`), the hook's store in `launch_notify_env` (`src/agent_notify.py`, whose docstring explains why `CDX_HOME` is pinned), and the companion's resolved command in the tray transport, which already has `CDX_TRAY_CDX` for naming it.
- The constraint that decides the design: a line on every command would be ignored within a day. The extra output belongs where the target is *not* the obvious one, and nowhere else.

# Plan
- [ ] 1. 1. Trace where the prefix, the store and the resolved binary are already known, and confirm each is available at the moment of reporting.
- [ ] 2. 2. Report the prefix in install, update and uninstall, and detect a session profile home.
- [ ] 3. 3. Extend tray doctor with the companion's resolved cdx and the hook's store, and name a mismatch.
- [ ] 4. 4. Add focused tests for redirected homes, inherited stores and a differing binary, then run project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_098_name_the_prefix_an_install_or_update_acted_on`
- `item_099_report_the_cdx_and_store_the_companion_actually_reaches`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_098_name_the_prefix_an_install_or_update_acted_on`. Proof deferred to slice closeout.
- request-AC2 -> `item_098_name_the_prefix_an_install_or_update_acted_on`. Proof deferred to slice closeout.
- request-AC4 -> `item_098_name_the_prefix_an_install_or_update_acted_on`. Proof deferred to slice closeout.
- request-AC5 -> `item_098_name_the_prefix_an_install_or_update_acted_on`. Proof deferred to slice closeout.
- request-AC6 -> `item_098_name_the_prefix_an_install_or_update_acted_on`. Proof deferred to slice closeout.
- request-AC3 -> `item_099_report_the_cdx_and_store_the_companion_actually_reaches`. Proof deferred to slice closeout.
- request-AC4 -> `item_099_report_the_cdx_and_store_the_companion_actually_reaches`. Proof deferred to slice closeout.
- request-AC5 -> `item_099_report_the_cdx_and_store_the_companion_actually_reaches`. Proof deferred to slice closeout.
- request-AC6 -> `item_099_report_the_cdx_and_store_the_companion_actually_reaches`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_050_say_which_installation_and_which_home_a_command_is_acting_on`
- Product brief(s): `prod_037_commands_that_name_what_they_are_about_to_touch`
- Architecture decision(s): (none yet)
