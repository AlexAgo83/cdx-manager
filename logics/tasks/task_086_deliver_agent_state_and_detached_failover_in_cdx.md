## task_086_deliver_agent_state_and_detached_failover_in_cdx - Deliver agent state and detached failover in cdx
> From version: 0.23.0
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
- Keywords: deliver, agent, state, detached, failover, cdx
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. State store and cdx agents first, behind its own setting.
- [ ] 2. Detached failover second.
- [ ] 3. Release, then consumers (remote-ops Jarvis HQ) read cdx agents --json.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_165_agent_state_store_and_cdx_agents`
- `item_166_failover_for_detached_runs`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_165_agent_state_store_and_cdx_agents`. Proof deferred to slice closeout.
- request-AC2 -> `item_165_agent_state_store_and_cdx_agents`. Proof deferred to slice closeout.
- request-AC3 -> `item_165_agent_state_store_and_cdx_agents`. Proof deferred to slice closeout.
- request-AC4 -> `item_165_agent_state_store_and_cdx_agents`. Proof deferred to slice closeout.
- request-AC6 -> `item_165_agent_state_store_and_cdx_agents`. Proof deferred to slice closeout.
- request-AC5 -> `item_166_failover_for_detached_runs`. Proof deferred to slice closeout.
- request-AC6 -> `item_166_failover_for_detached_runs`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`
- Product brief(s): `prod_057_agent_state_in_cdx`
- Architecture decision(s): (none yet)
