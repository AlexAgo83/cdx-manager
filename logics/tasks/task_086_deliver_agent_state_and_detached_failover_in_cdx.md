## task_086_deliver_agent_state_and_detached_failover_in_cdx - Deliver agent state and detached failover in cdx
> From version: 0.23.0
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: claude
> Indicators reviewed: 2026-10-28 08:46:27

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: deliver, agent, state, detached, failover, cdx
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. State store and cdx agents first, behind its own setting.
- [x] 2. Detached failover second.
- 3. External consumer adoption is outside repository delivery. Not planned, operator cleanup 2026-11-12. This closeout does not assert release publication or consumer adoption.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_165_agent_state_store_and_cdx_agents`
- `item_166_failover_for_detached_runs`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available in `logics/context-packs/agent_state_store.json`.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`
- request-AC2 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`
- request-AC3 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`
- request-AC4 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`
- request-AC6 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`
- request-AC5 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`
- request-AC6 -> This task. Proof: Implemented in de1460b (agent state, cdx agents) and 25efa79 (detached failover); validated with env -u RTK_DB_PATH npm test (1218 passed) and npm run lint. Source: `de1460b`

# Validation
- `env -u RTK_DB_PATH npm test`: 1218 passed (baseline 1208; the two RTK history tests fail only when the operator shell exports RTK_DB_PATH, before and after this change).
- `npm run lint`: all checks passed.
- `logics-manager review check`: 0 hits.
- Operator cleanup 2026-11-12: verified delivered code and git history de1460b and 25efa79; context-pack handoff exists at logics/context-packs/agent_state_store.json. External consumer adoption is not planned.
- Finish workflow executed on 2026-11-12.
- Linked backlog/request close verification passed.

# Report
- item_165 (de1460b): `src/agent_state.py` keeps one record per session under `$CDX_HOME/state/agents/<session>.json`, written atomically from `handle_notify` before and apart from any alert, so muted or off alerts still record. New per-session `--agent-state on|off` reuses notify provisioning (same hooks) with alerts suppressed for state-only sessions, and installs even where no notification channel exists (SSH, headless WSL). `UserPromptSubmit` is now subscribed on both providers for the `working` state and the prompt head (preview opt-in only). `limit` reuses run_failover (`_mentions_exhaustion` on the provider's typed error plus `status_confirms_exhaustion` on a refreshed status row via `_status_row_for`). `cdx agents [--max-age-hours N] [--json]` lists waiting first, deletes stale records, marks a record `ended` when the launching cdx pid (`CDX_AGENT_PID`) is gone.
- item_166 (25efa79): the detached child receives `--failover` and applies it on the existing blocking path, recording moves through `registry.migrate`; failover runs skip the native provider background path. The mutual-exclusion check and schema entry are gone.
- Decision: a separate `agent_state` setting rather than reusing `--notify`, because state-only sessions must not raise banners and must get hooks on hosts with no notification channel.
- Cleanup disposition 2026-11-12: external consumer adoption in plan step 3 is not planned; repository implementation is delivered. Known limits: `waiting` clears on the next prompt, tool activity or turn end (updated by commit 5800ca8); Codex has no failure hook, so Codex never reaches `failed`/`limit`; Codex plugins installed before this change keep their old hooks until reinstalled.
- Operator cleanup 2026-11-12: repository delivery is confirmed by commits de1460b and 25efa79 and the current src/agent_state.py, src/agent_notify.py and src/commands/runs.py implementations. Consumer adoption in another project is outside this repository and is not planned (Not planned, operator cleanup 2026-11-12). Closing this task records delivered repository work, not external adoption or publication evidence.
- Finished on 2026-11-12.
- Linked backlog item(s): `item_165_agent_state_store_and_cdx_agents`, `item_166_failover_for_detached_runs`
- Related request(s): `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`

# Links
- Request: `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`
- Product brief(s): `prod_057_agent_state_in_cdx`
- Architecture decision(s): (none yet)
