## task_047_orchestrate_tray_aware_cdx_agent_alert_delivery - Orchestrate tray-aware CDX agent alert delivery
> From version: 0.17.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-10 20:16:59

# AI Context
- Summary: Orchestrate tray-aware CDX agent alert delivery
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Blocked on task_046: this task consumes the companion, the cdx tray status snapshot, and the WSL bridge that task_046 builds. Do not start it while task_046 is open.
- The event spool remains a file, unlike the status snapshot. Its writer is a provider hook and its reader is the tray, two processes that never meet, so it cannot be a command invocation the way status is.
- Alert latency equals the poll period fixed in adr_005, so the delivery design is bounded by that decision rather than free to choose its own cadence.

# Plan
- [ ] 1. Confirm the base tray companion is available and trace the existing hook, compose_notification, direct-notification, and session-preference paths end to end.
- [ ] 2. Define and test the smallest local heartbeat, event, acknowledgement, expiry, and eviction protocol, preserving hook non-failure and existing privacy boundaries.
- [ ] 3. Route cdx notify through that protocol only for a live compatible tray, retaining the current direct OS notification fallback otherwise.
- [ ] 4. Implement tray-side hint, recent-event, and native-notification behaviour, including Windows installed-capability and permission handling.
- [ ] 5. Add the explicit Windows-to-WSL interop bridge, run focused and platform smoke checks, document the fallback semantics, and validate the workflow corpus.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC2 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC3 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC4 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC5 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC6 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC7 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC8 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC9 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.
- request-AC10 -> `item_082_deliver_agent_hook_events_through_the_active_cdx_tray_with_safe_fallback`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_036_route_cdx_agent_alerts_through_an_active_tray_companion`
- Product brief(s): `prod_025_tray_aware_agent_alerts`
- Architecture decision(s): `adr_005_cdx_tray_runtime_and_companion_transport_boundary`
