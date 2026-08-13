## task_068_orchestrate_conditional_reset_columns_in_cdx_status - Orchestrate conditional reset columns in cdx status
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: Codex

# AI Context
- Summary: Make reset columns signal-driven in terminal tables without changing status data contracts.
- Keywords: reset visibility, status table, disabled session, malformed value
- Use when: Implementing conditional reset columns in cdx status tables.
- Skip when: Changing JSON, detail output, or ranking behavior.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace normal, compact, detail, JSON, and ranking consumers of reset fields and pin the current fixed-column rendering with focused tests.
- [x] 2. Add the smallest per-column visibility calculation to the status-table renderer, reusing existing value formatting and preserving disabled-row alignment.
- [x] 3. Exercise all-hidden and mixed reset data in both table modes, then verify JSON, detail, and recommendation contracts remain untouched.
- [x] 4. Record validation evidence and update Logics documentation before closeout.
- [x] 5. Define visibility from renderable active-row signal only; cover no-session, disabled-only, numeric-string, and malformed bonus-reset values without changing ranking data.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_113_derive_reset_column_visibility_from_rendered_status_data`
- `item_114_prove_conditional_reset_columns_preserve_status_contracts`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof: `c455604`; empty reset headers are omitted.
- request-AC2 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof: `c455604`; each positive signal restores its matching column.
- request-AC3 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof: status table tests cover normal and small displays.
- request-AC5 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof: malformed reset values are ignored safely.
- request-AC3 -> `item_114_prove_conditional_reset_columns_preserve_status_contracts`. Proof: status test suite passed on 2026-08-13.
- request-AC4 -> `item_114_prove_conditional_reset_columns_preserve_status_contracts`. Proof: JSON and detailed views remain untouched by `c455604`.
- request-AC5 -> `item_114_prove_conditional_reset_columns_preserve_status_contracts`. Proof: project lint and Logics lint/audit passed.
- request-AC6 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof: `test_commands_status_py.py` covers disabled rows.
- request-AC7 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof: `test_commands_status_py.py` covers malformed values.

# Validation
- (no validation recorded yet)
- command: `node bin/python-runner.js -m unittest discover -s test -p 'test_commands_status_py.py' && npm run lint && logics-manager lint --require-status && logics-manager audit --group-by-doc` | result: passed | date: 2026-08-13
- Finish workflow executed on 2026-08-13.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-13.
- Linked backlog item(s): `item_113_derive_reset_column_visibility_from_rendered_status_data`, `item_114_prove_conditional_reset_columns_preserve_status_contracts`
- Related request(s): `req_057_hide_empty_reset_columns_from_cdx_status`

# Links
- Request: `req_057_hide_empty_reset_columns_from_cdx_status`
- Product brief(s): `prod_044_signal_only_cdx_status_reset_columns`
- Architecture decision(s): (none yet)
