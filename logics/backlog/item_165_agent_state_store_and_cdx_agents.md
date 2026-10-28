## item_165_agent_state_store_and_cdx_agents - Agent state store and cdx agents
> From version: 0.23.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 90%
> Complexity: Medium
> Theme: Agent state
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-10-28 08:41:07

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: agent, state, store, cdx, agents
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Hook events are turned into notifications and forgotten, so nothing can tell which session waits for its user.

# Scope
- In:
  - State record written from handle_notify, provisioning switch, cdx agents listing and JSON, limit state with reset time, tests and docs.
- Out:
  - Remote aggregation, UI.

# Acceptance criteria
- AC1: Every hook event cdx notify receives updates one small state record per cdx session (session, provider, cwd/project, state working|waiting|done|failed|limit, reason, last prompt head within the existing privacy rules, updated_at), written atomically under the cdx home, even when desktop alerts are muted or off.
- AC2: The hook needed for state is provisioned for every session that opts in (a setting distinct from desktop alerts, or notify on), for Claude Code and Codex.
- AC3: cdx agents [--json] lists the records, waiting first, drops records older than a configurable age, and marks a session whose process is gone as ended; nothing in it can change a hook decision (stdout stays silent in the hook path).
- AC4: A limit stop is recorded as state limit with the account's reset time when known, using the same two-signal rule as run_failover so a guess never marks a healthy session.
- AC6: Tests cover state transitions, muted alerts still recording, stale and ended sessions, the silent-stdout rule and detached failover; README/docs updated.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Every hook event cdx notify receives updates one small state record per cdx session (session, provider, cwd/project, state working|waiting|done|failed|limit, reason, last prompt head within the existing privacy rules, updated_at), written atomically under the cdx home, even when desktop alerts are muted or off.
- request-AC2 -> This backlog slice. Proof: AC2: The hook needed for state is provisioned for every session that opts in (a setting distinct from desktop alerts, or notify on), for Claude Code and Codex.
- request-AC3 -> This backlog slice. Proof: AC3: cdx agents [--json] lists the records, waiting first, drops records older than a configurable age, and marks a session whose process is gone as ended; nothing in it can change a hook decision (stdout stays silent in the hook path).
- request-AC4 -> This backlog slice. Proof: AC4: A limit stop is recorded as state limit with the account's reset time when known, using the same two-signal rule as run_failover so a guess never marks a healthy session.
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
- Priority: High - consumers are waiting on it
- Rationale: Set by scaffold input or defaulted for grooming.
