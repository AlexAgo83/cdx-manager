## task_068_orchestrate_conditional_reset_columns_in_cdx_status - Orchestrate conditional reset columns in cdx status
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 80%
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
- [ ] 1. Trace normal, compact, detail, JSON, and ranking consumers of reset fields and pin the current fixed-column rendering with focused tests.
- [ ] 2. Add the smallest per-column visibility calculation to the status-table renderer, reusing existing value formatting and preserving disabled-row alignment.
- [ ] 3. Exercise all-hidden and mixed reset data in both table modes, then verify JSON, detail, and recommendation contracts remain untouched.
- [ ] 4. Record validation evidence and update Logics documentation before closeout.
- [ ] 5. Define visibility from renderable active-row signal only; cover no-session, disabled-only, numeric-string, and malformed bonus-reset values without changing ranking data.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_113_derive_reset_column_visibility_from_rendered_status_data`
- `item_114_prove_conditional_reset_columns_preserve_status_contracts`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof deferred to slice closeout.
- request-AC2 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof deferred to slice closeout.
- request-AC3 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof deferred to slice closeout.
- request-AC5 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof deferred to slice closeout.
- request-AC3 -> `item_114_prove_conditional_reset_columns_preserve_status_contracts`. Proof deferred to slice closeout.
- request-AC4 -> `item_114_prove_conditional_reset_columns_preserve_status_contracts`. Proof deferred to slice closeout.
- request-AC5 -> `item_114_prove_conditional_reset_columns_preserve_status_contracts`. Proof deferred to slice closeout.
- request-AC6 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof deferred to slice closeout.
- request-AC7 -> `item_113_derive_reset_column_visibility_from_rendered_status_data`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_057_hide_empty_reset_columns_from_cdx_status`
- Product brief(s): `prod_044_signal_only_cdx_status_reset_columns`
- Architecture decision(s): (none yet)
