## task_086_deliver_agent_state_and_detached_failover_in_cdx - Deliver agent state and detached failover in cdx
> From version: 0.23.0
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 90%
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
- [ ] 3. Release, then consumers (remote-ops Jarvis HQ) read cdx agents --json.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_165_agent_state_store_and_cdx_agents`
- `item_166_failover_for_detached_runs`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
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

# Report
- item_165 (de1460b): `src/agent_state.py` keeps one record per session under `$CDX_HOME/state/agents/<session>.json`, written atomically from `handle_notify` before and apart from any alert, so muted or off alerts still record. New per-session `--agent-state on|off` reuses notify provisioning (same hooks) with alerts suppressed for state-only sessions, and installs even where no notification channel exists (SSH, headless WSL). `UserPromptSubmit` is now subscribed on both providers for the `working` state and the prompt head (preview opt-in only). `limit` reuses run_failover (`_mentions_exhaustion` on the provider's typed error plus `status_confirms_exhaustion` on a refreshed status row via `_status_row_for`). `cdx agents [--max-age-hours N] [--json]` lists waiting first, deletes stale records, marks a record `ended` when the launching cdx pid (`CDX_AGENT_PID`) is gone.
- item_166 (25efa79): the detached child receives `--failover` and applies it on the existing blocking path, recording moves through `registry.migrate`; failover runs skip the native provider background path. The mutual-exclusion check and schema entry are gone.
- Decision: a separate `agent_state` setting rather than reusing `--notify`, because state-only sessions must not raise banners and must get hooks on hosts with no notification channel.
- Open: plan step 3 (release, then remote-ops Jarvis HQ consumes `cdx agents --json`) is outside this repo run. Known limits: `waiting` holds until the next prompt or turn end (no per-tool hook); Codex has no failure hook, so Codex never reaches `failed`/`limit`; Codex plugins installed before this change keep their old hooks until reinstalled.

# Links
- Request: `req_081_keep_each_agent_session_s_state_and_expose_it_as_cdx_agents_json`
- Product brief(s): `prod_057_agent_state_in_cdx`
- Architecture decision(s): (none yet)
