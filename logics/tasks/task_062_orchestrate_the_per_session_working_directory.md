## task_062_orchestrate_the_per_session_working_directory - Orchestrate the per-session working directory
> From version: 0.18.5
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
- Keywords: orchestrate, per, session, working, directory
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. 1. Trace how the directory reaches each provider today, interactively and headlessly, and where the other launch settings are stored and rendered.
- [ ] 2. 2. Add the setting, its validation, and its place in the configuration and JSON surfaces.
- [ ] 3. 3. Honour it at launch with a per-launch override, and refuse before starting a provider when it has gone.
- [ ] 4. 4. Add focused tests per provider for recorded, overridden, absent and missing; then run project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_100_record_and_honour_a_per_session_working_directory`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC2 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC3 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC4 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC5 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC6 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.
- request-AC7 -> `item_100_record_and_honour_a_per_session_working_directory`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_051_launch_a_session_in_the_directory_it_belongs_to`
- Product brief(s): `prod_038_sessions_that_know_what_they_are_working_on`
- Architecture decision(s): (none yet)
