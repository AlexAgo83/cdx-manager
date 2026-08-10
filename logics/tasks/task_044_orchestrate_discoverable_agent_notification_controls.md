## task_044_orchestrate_discoverable_agent_notification_controls - Orchestrate discoverable agent notification controls
> From version: 0.17.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: Codex

# AI Context
- Summary: Orchestrate discoverable agent notification controls
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace root usage, main-screen shortcuts, notify dispatch, settings rendering, and launch provisioning to retain one source of lifecycle truth.
- [x] 2. Add the smallest task-oriented help and direct-hook guidance without introducing a new command surface.
- [x] 3. Add focused notify preference feedback on set and unset, then make configuration labels and README examples agree with it.
- [x] 4. Reconcile launch-time messaging with the actual provisioning result and required review path, without adding persistent state.
- [x] 5. Add focused regression tests, run project validation, and record the implementation handoff context.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`
- request-AC2 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`
- request-AC3 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`
- request-AC4 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`
- request-AC5 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`
- request-AC6 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`
- request-AC7 -> This task. Proof: Implemented in 5ac64ca; validated with npm run lint and npm test -- --quiet. Source: `5ac64ca`

# Validation
- (no validation recorded yet)
- command: `npm run lint && npm test -- --quiet` | result: passed | date: 2026-08-10
- Finish workflow executed on 2026-08-10.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-10.
- Linked backlog item(s): `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`
- Related request(s): `req_033_make_agent_notification_controls_discoverable_and_self_explanatory`

# Links
- Request: `req_033_make_agent_notification_controls_discoverable_and_self_explanatory`
- Product brief(s): `prod_023_clear_notification_controls`
- Architecture decision(s): (none yet)
