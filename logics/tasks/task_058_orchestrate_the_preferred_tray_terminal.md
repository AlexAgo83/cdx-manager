## task_058_orchestrate_the_preferred_tray_terminal - Orchestrate the preferred tray terminal
> From version: 0.18.4
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
- Keywords: orchestrate, preferred, tray, terminal
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. 1. Trace how each backend opens a terminal today and what the snapshot already carries.
- [ ] 2. 2. Define the smallest validated preference that cannot express a command, and the CDX surface to set, show and clear it.
- [ ] 3. 3. Carry it through the snapshot and honour it per platform, with a fallback to today's behaviour.
- [ ] 4. 4. Add focused tests for each outcome and document what the setting cannot do.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`. Proof deferred to slice closeout.
- request-AC2 -> `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`. Proof deferred to slice closeout.
- request-AC3 -> `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`. Proof deferred to slice closeout.
- request-AC4 -> `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`. Proof deferred to slice closeout.
- request-AC5 -> `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`. Proof deferred to slice closeout.
- request-AC6 -> `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_047_let_the_operator_choose_which_terminal_the_tray_opens`
- Product brief(s): `prod_034_the_tray_opens_the_terminal_you_actually_use`
- Architecture decision(s): (none yet)
