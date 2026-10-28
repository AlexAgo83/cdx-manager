## prod_057_agent_state_in_cdx - Agent state in cdx
> Date: 2026-10-28
> Status: Proposed
> Related request: `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`
> Related backlog: `item_165_agent_state_store_and_cdx_agents`, `item_166_failover_for_detached_runs`
> Related task: `task_086_deliver_agent_state_and_detached_failover_in_cdx`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
cdx already sees every agent event through its hook; keep the latest state per session and expose it so other tools can orchestrate without scraping.

# Goals
- One cheap, local answer to: which session needs me, which is busy, which hit a limit.
- Detached background runs survive a usage limit like attached ones.

# Non-goals
- A dashboard or UI in cdx itself beyond the CLI listing.
- Shipping state between machines: consumers fetch cdx agents --json where they need it.

# Scope and guardrails
- In: scaffolded request, product, backlog, orchestration task, validation, and handoff context.
- Out: unrelated workflow docs and implementation of generated tasks.

# Key product decisions
- Use structured input as the source of truth for generated docs.
- Keep generated write paths local and repo-bounded.

# Success signals
- Generated docs pass lint and audit without broad manual rewrites.
- Context-pack output can be handed to an implementation agent directly.

# References
- Product back-reference: `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`
- Task back-reference: `task_086_deliver_agent_state_and_detached_failover_in_cdx`
