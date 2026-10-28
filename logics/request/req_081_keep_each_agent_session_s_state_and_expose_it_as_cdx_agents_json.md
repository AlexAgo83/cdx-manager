## req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json - Keep each agent session's state and expose it as cdx agents --json
> From version: 0.23.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Agent state
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: each, agent, session, state, expose, cdx, agents, json
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- A dashboard or another tool (a hub, a terminal board, a chat agent) can ask cdx which sessions are working, waiting for their user, done or stopped by a usage limit, without parsing transcripts or terminals.

# Context
- cdx notify already receives every Claude Code and Codex hook event with the cdx session name, but only turns it into a desktop or tray notification and keeps nothing.
- Consumers seen so far: a web hub across several machines, a chat agent driving cdx through MCP, terminal boards built on cdx.
- cdx run --failover cannot be combined with --detach, so background runs started detached never fail over on a usage limit.

# Acceptance criteria
- AC1: Every hook event cdx notify receives updates one small state record per cdx session (session, provider, cwd/project, state working|waiting|done|failed|limit, reason, last prompt head within the existing privacy rules, updated_at), written atomically under the cdx home, even when desktop alerts are muted or off.
- AC2: The hook needed for state is provisioned for every session that opts in (a setting distinct from desktop alerts, or notify on), for Claude Code and Codex.
- AC3: cdx agents [--json] lists the records, waiting first, drops records older than a configurable age, and marks a session whose process is gone as ended; nothing in it can change a hook decision (stdout stays silent in the hook path).
- AC4: A limit stop is recorded as state limit with the account's reset time when known, using the same two-signal rule as run_failover so a guess never marks a healthy session.
- AC5: --failover works with --detach: the detached supervisor applies the failover decision, and the run registry records the move.
- AC6: Tests cover state transitions, muted alerts still recording, stale and ended sessions, the silent-stdout rule and detached failover; README/docs updated.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_057_agent_state_in_cdx`
- Architecture decision(s): (none yet)

# References
- src/agent_notify.py
- src/run_failover.py
- src/run_registry.py
- src/cli_args.py

# Backlog
- `item_165_agent_state_store_and_cdx_agents`
- `item_166_failover_for_detached_runs`
