## item_166_failover_for_detached_runs - Failover for detached runs
> From version: 0.23.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Agent state
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: failover, detached, runs
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- --failover needs a watching process, which --detach gives up, so detached runs never move to another account.

# Scope
- In:
  - Failover decision applied by the detached supervisor, registry entry for the move, tests.
- Out:
  - Changing the two-signal failover rule.

# Acceptance criteria
- AC5: --failover works with --detach: the detached supervisor applies the failover decision, and the run registry records the move.
- AC6: Tests cover state transitions, muted alerts still recording, stale and ended sessions, the silent-stdout rule and detached failover; README/docs updated.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC5: --failover works with --detach: the detached supervisor applies the failover decision, and the run registry records the move.
- request-AC6 -> This backlog slice. Proof: AC6: Tests cover state transitions, muted alerts still recording, stale and ended sessions, the silent-stdout rule and detached failover; README/docs updated.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_057_agent_state_in_cdx`
- Architecture decision(s): (none yet)
- Request: `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`
- Primary task(s): `task_086_deliver_agent_state_and_detached_failover_in_cdx`

# Priority
- Priority: Medium - unattended runs die on a usage limit
- Rationale: Set by scaffold input or defaulted for grooming.
