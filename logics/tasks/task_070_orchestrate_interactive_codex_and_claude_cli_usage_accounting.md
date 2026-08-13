## task_070_orchestrate_interactive_codex_and_claude_cli_usage_accounting - Orchestrate interactive Codex and Claude CLI usage accounting
> From version: 0.19.1
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
- Keywords: orchestrate, interactive, codex, claude, cli, usage, accounting
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace current headless usage persistence, interactive launch lifecycle, hook provisioning, and history/statistics contracts.
- [ ] 2. Implement and test tolerant provider transcript readers plus idempotent snapshot handling for Codex and Claude.
- [ ] 3. Wire accounting hooks and persistence into interactive launches without coupling them to notification opt-in, then prove existing history and statistics commands expose the records.
- [ ] 4. Update concise user documentation, run focused checks and project validation, then validate the completed Logics chain.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_117_capture_and_normalize_interactive_provider_token_snapshots`
- `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_117_capture_and_normalize_interactive_provider_token_snapshots`. Proof deferred to slice closeout.
- request-AC2 -> `item_117_capture_and_normalize_interactive_provider_token_snapshots`. Proof deferred to slice closeout.
- request-AC3 -> `item_117_capture_and_normalize_interactive_provider_token_snapshots`. Proof deferred to slice closeout.
- request-AC5 -> `item_117_capture_and_normalize_interactive_provider_token_snapshots`. Proof deferred to slice closeout.
- request-AC6 -> `item_117_capture_and_normalize_interactive_provider_token_snapshots`. Proof deferred to slice closeout.
- request-AC3 -> `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`. Proof deferred to slice closeout.
- request-AC4 -> `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`. Proof deferred to slice closeout.
- request-AC5 -> `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`. Proof deferred to slice closeout.
- request-AC6 -> `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_059_record_interactive_codex_and_claude_cli_token_usage`
- Product brief(s): `prod_046_interactive_cli_usage_accounting`
- Architecture decision(s): (none yet)
