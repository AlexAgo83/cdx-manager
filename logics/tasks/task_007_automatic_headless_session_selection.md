## task_007_automatic_headless_session_selection - Automatic headless session selection
> From version: 0.6.5
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Integration
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Derived from backlog item `item_007_automatic_headless_session_selection`.
- Source file: `logics/backlog/item_007_automatic_headless_session_selection.md`.
- Related request(s): `req_000_orchestia_headless_json_task_runner`.
- Orchestia wants cdx-manager to choose a suitable account/session from provider, readiness, cooldown, quota, and priority data.

```mermaid
%% logics-kind: task
%% logics-signature: task|automatic-headless-session-selection|item-007-automatic-headless-session-sele|1-define-a-reusable-selection-service|npm-run-lint
stateDiagram-v2
    state "item_007_automatic_headless_session_selection" as Backlog
    state "1. Design selection policy and JSON schema" as Scope
    state "2. Implement cdx select" as Build
    state "3. Reuse selector from cdx run" as Verify
    state "npm test and npm run lint" as Validation
    state "Done report" as Report
    [*] --> Backlog
    Backlog --> Scope
    Scope --> Build
    Build --> Verify
    Verify --> Validation
    Validation --> Report
    Report --> [*]
```

# Plan
- [x] 1. Define a reusable selection service that consumes existing session, provider, auth, quota, cooldown, and readiness data.
- [x] 2. Implement `cdx select --provider PROVIDER --min-reasoning-effort LEVEL --require-ready --json`.
- [x] 3. Keep `--min-power LEVEL` as a compatibility alias.
- [x] 4. Apply deterministic ranking: provider match, readiness, cooldown avoidance, healthiest quota/availability, configured priority, then session name.
- [x] 5. Return stable JSON with `ok`, `session`, `provider`, `reason`, `selection_policy`, warnings, and error fields.
- [x] 6. Return `ok: false` with `error.source: "cdx"` when no suitable session exists.
- [x] 7. Wire `cdx run --provider codex` to the same selector once the run command is available.
- [x] 8. Add tests for ready selection, readiness exclusion, cooldown/quota ranking, alias behavior, deterministic tie-breaking, no-match error, and run-command reuse.
- [x] 9. Update README/help docs and linked Logics docs.
- [x] CHECKPOINT: leave the current wave commit-ready and update linked Logics docs before continuing.
- [x] GATE: do not close the task until relevant tests and lint pass.

# Validation
- `npm run lint`
- `npm test`
- Focused tests for `cdx select` JSON output and selection ordering.
- Focused test for `cdx run --provider` reusing the selector.

# AC Traceability
- AC1 -> Plan: core `cdx select` JSON command.
- AC2 -> Plan: `--min-power` alias.
- AC3 -> Plan: readiness exclusion.
- AC4 -> Plan: deterministic ranking.
- AC5 -> Plan: no-suitable-session error contract.
- AC6 -> Plan: reusable selector for `cdx run --provider`.

# Decision framing
- Product framing: Consider
- Product signals: Orchestia delegates account choice to cdx-manager.
- Product follow-up: Document ranking policy.
- Architecture framing: Required
- Architecture signals: shared selector, readiness data contract, ranking determinism.
- Architecture follow-up: Link ADR if ranking becomes configurable.

# Links
- Product brief(s): `prod_002_headless_automation_contract_for_orchestia`
- Architecture decision(s): `adr_002_provider_native_headless_run_boundary`
- Derived from `item_007_automatic_headless_session_selection`
- Request(s): `req_000_orchestia_headless_json_task_runner`

# AI Context
- Summary: Implement `cdx select` and a reusable deterministic session selector for provider-based headless automation.
- Keywords: cdx select, provider, readiness, quota, cooldown, ranking, min-reasoning-effort, Orchestia
- Use when: Implementing account/session selection.
- Skip when: Work is only about executing provider processes or artifact capture.

# Risks & rollback
- Risk: Automatic selection can choose an unavailable or lower-priority account if readiness, cooldown, or quota signals are misread.
- Mitigation: Keep ranking deterministic, expose selection reasons in JSON, and test readiness exclusion, cooldown ranking, and tie-breaking.
- Rollback: Revert selector reuse and require explicit `--session` for headless runs until selection policy is corrected.

# Definition of Done (DoD)
- [x] Scope implemented and acceptance criteria covered.
- [x] Validation commands executed and results captured.
- [x] Linked request/backlog/task docs updated.
- [x] Status is `Done` and progress is `100%`.

# Report
- Implemented `cdx select --json`, `--min-reasoning-effort`, `--min-power` aliasing, no-match JSON errors, and provider-based auto-selection for `cdx run`.
- Validation evidence:
  - `python -m unittest discover -s test -p 'test_cli_py.py' -k 'select'`
  - `python -m unittest discover -s test -p 'test_cli_py.py' -k 'run_'`
