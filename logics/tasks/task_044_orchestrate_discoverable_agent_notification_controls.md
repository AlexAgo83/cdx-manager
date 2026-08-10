## task_044_orchestrate_discoverable_agent_notification_controls - Orchestrate discoverable agent notification controls
> From version: 0.17.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Orchestrate discoverable agent notification controls
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace root usage, main-screen shortcuts, notify dispatch, settings rendering, and launch provisioning to retain one source of lifecycle truth.
- [ ] 2. Add the smallest task-oriented help and direct-hook guidance without introducing a new command surface.
- [ ] 3. Add focused notify preference feedback on set and unset, then make configuration labels and README examples agree with it.
- [ ] 4. Reconcile launch-time messaging with the actual provisioning result and required review path, without adding persistent state.
- [ ] 5. Add focused regression tests, run project validation, and record the implementation handoff context.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.
- request-AC2 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.
- request-AC3 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.
- request-AC4 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.
- request-AC5 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.
- request-AC6 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.
- request-AC7 -> `item_077_clarify_notification_setup_lifecycle_feedback_and_documentation`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_033_make_agent_notification_controls_discoverable_and_self_explanatory`
- Product brief(s): `prod_023_clear_notification_controls`
- Architecture decision(s): (none yet)
