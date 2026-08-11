## task_059_orchestrate_the_repository_aware_logics_card - Orchestrate the repository-aware Logics card
> From version: 0.18.5
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:47:58
> Owner: Codex

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
- SETTLED: the summary aggregates across repositories and says how many there are — "3 repositories · 2 blocked" — while the two rows come from the most constrained repository alone, each prefixed with that repository's name. A row therefore always says what it is about, and the bound of two rows that `req_037` AC3 fixed is kept.
- Rejected: one summary line per repository, which shows everything and leaves no row to click through to a document; and lifting the two-row bound, which contradicts `req_037` AC3 and turns a menu into a log.

# Plan
- [x] 1. 1. Reproduce the absence: request the snapshot from a project, from a home directory, and from /.
- [x] 2. 2. Add the smallest durable setting for the repository path, beside the other tray preferences.
- [x] 3. 3. Run the adapter against it, keeping silence as the answer for everything unavailable.
- [x] 4. 4. Add focused tests for named, missing, not-a-repository and unset, then run project validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_096_name_the_repository_the_logics_card_reports_on`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: active runtime directories select the repository in `0ccf23a`.
- request-AC2 -> This task. Proof: repository roots are derived at card read time in `0ccf23a`.
- request-AC3 -> This task. Proof: no recorded repository yields no card, without a current-directory fallback.
- request-AC4 -> This task. Proof: all active repositories are aggregated in the card summary.
- request-AC5 -> This task. Proof: selected rows include only the repository basename.
- request-AC6 -> This task. Proof: focused tray adapter tests passed in `0ccf23a`.
- request-AC7 -> This task. Proof: focused tray adapter tests passed in `0ccf23a`.

# Validation
- (no validation recorded yet)
- command: `npm run test:py -- test/test_tray_plugins_py.py && npm run lint` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_096_name_the_repository_the_logics_card_reports_on`
- Related request(s): `req_048_give_the_logics_tray_card_a_repository_to_report_on`

# Links
- Request: `req_048_give_the_logics_tray_card_a_repository_to_report_on`
- Product brief(s): `prod_035_a_logics_card_that_knows_which_repository_it_is_about`
- Architecture decision(s): (none yet)
