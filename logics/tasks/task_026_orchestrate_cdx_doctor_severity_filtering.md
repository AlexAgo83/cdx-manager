## task_026_orchestrate_cdx_doctor_severity_filtering - Orchestrate cdx doctor severity filtering
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-05

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Inspect current doctor parser, report data shape, formatter, JSON envelope, and health tests.
- [ ] 2. Add a single validated severity parser and a small report-filter helper with normalized status semantics.
- [ ] 3. Wire the filter into text and JSON paths after collection; retain unfiltered behavior.
- [ ] 4. Update help/README and add precise CLI tests including empty matches and invalid flags.
- [ ] 5. Run focused tests, full relevant test/lint checks, and Logics validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_035_filter_cdx_doctor_report_by_severity`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- AC1 -> This task. Proof: severity parsing accepts canonical OK/WARN/FAIL values case-insensitively.
- AC2 -> This task. Proof: JSON output keeps the success envelope and reports filtered issues, summary, and normalized severity.
- AC3 -> This task. Proof: text output and summaries reflect only the requested severity, including empty matches.
- AC4 -> This task. Proof: invalid severity usage is rejected while unfiltered doctor output remains backward compatible.
- AC5 -> This task. Proof: help, README, and focused tests cover the accepted values, invalid input, text output, and JSON output.

# Validation
- (no validation recorded yet)
- Finish workflow executed on 2026-08-05.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-05.
- Linked backlog item(s): `item_035_filter_cdx_doctor_report_by_severity`
- Related request(s): `req_015_add_a_severity_filter_to_cdx_doctor`

# AI Context
- Summary: Orchestrate cdx doctor severity filtering
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_015_add_a_severity_filter_to_cdx_doctor`
- Product brief(s): `prod_008_filterable_doctor_diagnostics`
- Architecture decision(s): (none yet)
