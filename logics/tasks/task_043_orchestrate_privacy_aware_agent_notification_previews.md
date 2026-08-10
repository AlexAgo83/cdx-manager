## task_043_orchestrate_privacy_aware_agent_notification_previews - Orchestrate privacy-aware agent notification previews
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
- Summary: Orchestrate privacy-aware agent notification previews
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Read the current notification, settings, launch, and provider-provisioning paths; confirm current hook schemas against provider documentation before changing generated event names.
- [x] 2. Add the minimal explicit per-session preview preference by following the existing notify setting end to end, including unset, display, and bulk behavior.
- [x] 3. Implement one small pure preview helper at the shared notification composition boundary; keep it Stop-only, bounded, single-line, and safe when the payload lacks a usable message.
- [x] 4. Refine completion and permission-attention wording from documented event metadata without passing arbitrary tool input or assistant text to attention notifications.
- [x] 5. Update provider hook provisioning only where required by documented event support, preserving idempotence, user-owned configuration, and non-failing hooks.
- [x] 6. Add focused regression tests and README guidance, then run project validation, Logics lint, audit, and request-chain validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_076_add_opt_in_bounded_assistant_response_previews_to_agent_notifications`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`
- request-AC2 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`
- request-AC3 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`
- request-AC4 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`
- request-AC5 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`
- request-AC6 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`
- request-AC7 -> This task. Proof: Implemented in 65e6fd7 and 2106232; validated with npm run lint and npm test -- --quiet. Source: `2106232`

# Validation
- (no validation recorded yet)
- command: `npm run lint && npm test -- --quiet` | result: passed | date: 2026-08-10
- Finish workflow executed on 2026-08-10.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-10.
- Linked backlog item(s): `item_076_add_opt_in_bounded_assistant_response_previews_to_agent_notifications`
- Related request(s): `req_032_show_a_privacy_aware_preview_in_agent_completion_notifications`

# Links
- Request: `req_032_show_a_privacy_aware_preview_in_agent_completion_notifications`
- Product brief(s): `prod_022_actionable_private_agent_notifications`
- Architecture decision(s): (none yet)
