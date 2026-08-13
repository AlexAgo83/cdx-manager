## task_070_orchestrate_interactive_codex_and_claude_cli_usage_accounting - Orchestrate interactive Codex and Claude CLI usage accounting
> From version: 0.19.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: codex

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, interactive, codex, claude, cli, usage, accounting
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace current headless usage persistence, interactive launch lifecycle, hook provisioning, and history/statistics contracts.
- [x] 2. Implement and test tolerant provider transcript readers plus idempotent snapshot handling for Codex and Claude.
- [x] 3. Wire accounting and persistence into interactive completion without coupling them to notification opt-in, then prove existing history and statistics commands expose the records.
- [x] 4. Update concise user documentation, run focused checks and project validation, then validate the completed Logics chain.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_117_capture_and_normalize_interactive_provider_token_snapshots`
- `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Codex parser selects the latest cumulative token_count snapshot and preserves cache and reasoning fields.
- request-AC2 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Claude parser sums unique assistant UUIDs and keeps cache totals separate from provider total.
- request-AC3 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_commands_launch_py.py test/test_runtime_py.py` | result: passed | Interactive launch attaches best-effort provider transcript usage after the provider process returns, including error completion.
- request-AC5 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Malformed records and transcripts older than the launch are ignored without storing usage or changing the launch outcome.
- request-AC6 -> This task. Proof: date: 2026-08-13 | command: `npm test && npm run lint` | result: passed | Focused parser and launch checks passed; full project test suite and lint also passed.
- request-AC3 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_commands_launch_py.py test/test_runtime_py.py` | result: passed | Interactive launch attaches best-effort provider transcript usage after the provider process returns, including error completion.
- request-AC4 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_commands_launch_py.py` | result: passed | Launch history receives the existing usage object, so existing history JSON and statistics aggregation remain the retrieval surface.
- request-AC5 -> This task. Proof: date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Malformed records and transcripts older than the launch are ignored without storing usage or changing the launch outcome.
- request-AC6 -> This task. Proof: date: 2026-08-13 | command: `npm test && npm run lint` | result: passed | Focused parser and launch checks passed; full project test suite and lint also passed.

# Validation
- (no validation recorded yet)
- npm test and npm run lint passed on 2026-08-13: 891 tests passed; lint passed
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_117_capture_and_normalize_interactive_provider_token_snapshots`, `item_118_persist_interactive_usage_in_existing_cdx_history_and_statistics`
- Related request(s): `req_059_record_interactive_codex_and_claude_cli_token_usage`

# Links
- Request: `req_059_record_interactive_codex_and_claude_cli_token_usage`
- Product brief(s): `prod_046_interactive_cli_usage_accounting`
- Architecture decision(s): (none yet)

# Evidence
- AC1 | date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Codex parser selects the latest cumulative token_count snapshot and preserves cache and reasoning fields.
- AC2 | date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Claude parser sums unique assistant UUIDs and keeps cache totals separate from provider total.
- AC3 | date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_commands_launch_py.py test/test_runtime_py.py` | result: passed | Interactive launch attaches best-effort provider transcript usage after the provider process returns, including error completion.
- AC4 | date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_commands_launch_py.py` | result: passed | Launch history receives the existing usage object, so existing history JSON and statistics aggregation remain the retrieval surface.
- AC5 | date: 2026-08-13 | command: `npm run test:py -- --quiet test/test_interactive_usage_py.py` | result: passed | Malformed records and transcripts older than the launch are ignored without storing usage or changing the launch outcome.
- AC6 | date: 2026-08-13 | command: `npm test && npm run lint` | result: passed | Focused parser and launch checks passed; full project test suite and lint also passed.
