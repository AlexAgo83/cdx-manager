## task_059_orchestrate_the_repository_aware_logics_card - Orchestrate the repository-aware Logics card
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 85%
> Confidence: 75%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:40:11

# AI Context
- Summary: Blocked on req_051: the run directories it records are the only source this card can read.
- Keywords: Logics card, derived repository, adr_007, blocked on req_051
- Use when: Implementing req_048, after req_051 has landed.
- Skip when: Starting before run directories are recorded; there is nothing reliable to read until then.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Blocked on `task_062`. The directories it records on each run are the only trustworthy source for this card; starting first means reading where a process happens to be, which is the bug being fixed.
- The defect, measured after release: `cdx tray status` reports the card from inside a Logics repository and reports nothing from a home directory or from `/`. `_status` in `src/tray_logics.py` runs `logics-manager status --format json` as a subprocess, so it answers about the caller's working directory — and a companion started at login has none. Every existing test injects the status JSON, so none of them exercises this.
- `adr_007` governs what may be read and what may cross: derive the repository at read time, never store it beside the path, and let only a basename reach the companion.
- Open design, to settle before writing any rendering: when several repositories are in play, how a row says which one it belongs to. Merging counts across repositories describes neither, and the card has at most two rows to spend.

# Plan
- [ ] 1. 1. Reproduce the absence: request the snapshot from a project, from a home directory, and from /.
- [ ] 2. 2. Add the smallest durable setting for the repository path, beside the other tray preferences.
- [ ] 3. 3. Run the adapter against it, keeping silence as the answer for everything unavailable.
- [ ] 4. 4. Add focused tests for named, missing, not-a-repository and unset, then run project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_096_name_the_repository_the_logics_card_reports_on`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_096_name_the_repository_the_logics_card_reports_on`. Proof deferred to slice closeout.
- request-AC2 -> `item_096_name_the_repository_the_logics_card_reports_on`. Proof deferred to slice closeout.
- request-AC3 -> `item_096_name_the_repository_the_logics_card_reports_on`. Proof deferred to slice closeout.
- request-AC4 -> `item_096_name_the_repository_the_logics_card_reports_on`. Proof deferred to slice closeout.
- request-AC5 -> `item_096_name_the_repository_the_logics_card_reports_on`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_048_give_the_logics_tray_card_a_repository_to_report_on`
- Product brief(s): `prod_035_a_logics_card_that_knows_which_repository_it_is_about`
- Architecture decision(s): (none yet)
