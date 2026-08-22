## task_077_orchestrate_truthful_codex_authentication_health_signals - Orchestrate truthful Codex authentication health signals
> From version: 0.20.4
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-22 12:04:08
> Owner: Codex

# AI Context
- Summary: Deliver safe, explicit authentication outcomes across doctor, bulk refresh, documentation, and tests.
- Keywords: orchestrate, truthful, codex, authentication, health, signals
- Use when: Coordinating the three bounded authentication observability slices in this request chain.
- Skip when: Repairing a credential or operating a host scheduler directly.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Trace the existing refresh result, live diagnostic, enabled-state, and scheduler-facing exit-code paths.
- [x] 2. Centralize the token-safe authentication-failure classification and apply it to the doctor result contract.
- [x] 3. Filter disabled sessions only in the bulk refresh selection while retaining explicit named checks.
- [x] 4. Define and implement the all-locked result without changing the lock ownership behavior.
- [x] 5. Add focused contract tests, update documentation, run project validation, and record task evidence.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_135_classify_live_codex_diagnostic_failures_safely`
- `item_136_exclude_disabled_profiles_from_bulk_codex_refresh`
- `item_137_make_all_locked_bulk_refresh_results_explicit`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_135_classify_live_codex_diagnostic_failures_safely`. Proof deferred to slice closeout.
- request-AC4 -> `item_135_classify_live_codex_diagnostic_failures_safely`. Proof deferred to slice closeout.
- request-AC2 -> `item_136_exclude_disabled_profiles_from_bulk_codex_refresh`. Proof deferred to slice closeout.
- request-AC4 -> `item_136_exclude_disabled_profiles_from_bulk_codex_refresh`. Proof deferred to slice closeout.
- request-AC3 -> `item_137_make_all_locked_bulk_refresh_results_explicit`. Proof deferred to slice closeout.
- request-AC4 -> `item_137_make_all_locked_bulk_refresh_results_explicit`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_068_harden_codex_authentication_observability`
- Product brief(s): `prod_051_truthful_codex_authentication_health_signals`
- Architecture decision(s): (none yet)
