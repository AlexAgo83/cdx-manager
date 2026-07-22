## task_023_orchestrate_optional_session_labels - Orchestrate optional session labels
> From version: 0.11.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Start with the session-service data model: add label validation, root-level persistence, and service methods for set and clear.
- [ ] 2. Propagate label into list and status row builders without changing sort order, priority selection, auth checks, launch settings, or runtime state.
- [ ] 3. Add the dedicated `cdx label` parser and handler, wire it into the command registry, and return concise text and JSON responses.
- [ ] 4. Add conditional `LABEL` columns to the default list and full status formatters, leaving no-label and small-status output compact.
- [ ] 5. Preserve labels in copy, rename, export, and import paths.
- [ ] 6. Update help and README documentation.
- [ ] 7. Run focused CLI and service tests, then the relevant unittest files.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_032_optional_session_labels_in_cli_list_and_status_surfaces`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: scaffold command generated the request-chain corpus.
- request-AC4 -> This task. Proof: optional context-pack handoff is supported.
- request-AC6 -> This task. Proof: dry-run and collision checks bound file changes.
- request-AC8 -> This task. Proof: CLI help documents the one-pass scaffold workflow.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run scaffold command tests.

# Report
- Implementation complete.

# AI Context
- Summary: Orchestrate optional session labels
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_012_add_optional_labels_to_cdx_sessions`
- Product brief(s): `prod_005_session_labeling_for_cdx`
- Architecture decision(s): (none yet)
