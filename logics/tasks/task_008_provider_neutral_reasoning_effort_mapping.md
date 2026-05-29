## task_008_provider_neutral_reasoning_effort_mapping - Provider-neutral reasoning effort mapping
> From version: 0.6.5
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 82%
> Progress: 100%
> Complexity: Medium
> Theme: Integration
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Derived from backlog item `item_008_provider_neutral_reasoning_effort_mapping`.
- Source file: `logics/backlog/item_008_provider_neutral_reasoning_effort_mapping.md`.
- Related request(s): `req_000_orchestia_headless_json_task_runner`.
- Orchestia confirmed `--reasoning-effort low|medium|high` as the stable public name, with `--power` retained as a cdx alias.

```mermaid
%% logics-kind: task
%% logics-signature: task|provider-neutral-reasoning-effort-mappin|item-008-provider-neutral-reasoning-effo|1-add-a-central-normalization-helper|npm-run-lint
stateDiagram-v2
    state "item_008_provider_neutral_reasoning_effort_mapping" as Backlog
    state "1. Design normalization helper" as Scope
    state "2. Map effort to Codex launch options" as Build
    state "3. Preserve provider-neutral JSON contract" as Verify
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
- [x] 1. Add a central normalization helper for `--reasoning-effort` and `--power`.
- [x] 2. Validate allowed values `low`, `medium`, and `high`.
- [x] 3. Reject conflicting `--reasoning-effort` and `--power` values with `error.source: "cdx"`.
- [x] 4. Map normalized effort to Codex launch options.
- [x] 5. Return resolved `reasoning_effort` and `power` in `cdx run` and selection JSON responses.
- [x] 6. Leave explicit extension points for Claude/Ollama mappings without changing the public schema.
- [x] 7. Add tests for preferred option, alias option, conflict handling, invalid values, Codex mapping, and response fields.
- [x] 8. Update CLI help/README and linked Logics docs.
- [x] CHECKPOINT: leave the current wave commit-ready and update linked Logics docs before continuing.
- [x] GATE: do not close the task until relevant tests and lint pass.

# Validation
- `npm run lint`
- `npm test`
- Focused parser/normalization tests for reasoning effort and power alias behavior.
- Focused Codex launch option test.

# AC Traceability
- AC1 -> Plan: preferred `--reasoning-effort`.
- AC2 -> Plan: `--power` alias.
- AC3 -> Plan: conflict validation.
- AC4 -> Plan: Codex mapping.
- AC5 -> Plan: JSON response fields.
- AC6 -> Plan: provider-neutral extension points.

# Decision framing
- Product framing: Consider
- Product signals: public automation terminology must stay stable.
- Product follow-up: Update docs and help text.
- Architecture framing: Required
- Architecture signals: provider option normalization and launch mapping.
- Architecture follow-up: Link ADR if provider mappings become extensive.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Derived from `item_008_provider_neutral_reasoning_effort_mapping`
- Request(s): `req_000_orchestia_headless_json_task_runner`

# AI Context
- Summary: Implement `--reasoning-effort` as the provider-neutral public option and keep `--power` as an alias mapped to Codex launch options.
- Keywords: reasoning-effort, power, alias, Codex, model_reasoning_effort, provider-neutral
- Use when: Implementing or testing provider effort option handling.
- Skip when: Work is only about selection ranking or artifact output.

# Risks & rollback
- Risk: Effort normalization can send the wrong provider launch option or accept conflicting public aliases.
- Mitigation: Normalize `--reasoning-effort` and `--power` centrally, reject conflicts, and test preferred, alias, invalid, and mapped Codex launch values.
- Rollback: Revert the normalization helper and require the previous provider-specific option path until mappings are corrected.

# Definition of Done (DoD)
- [x] Scope implemented and acceptance criteria covered.
- [x] Validation commands executed and results captured.
- [x] Linked request/backlog/task docs updated.
- [x] Status is `Done` and progress is `100%`.

# Report
- Implemented normalized `--reasoning-effort` handling with `--power` alias support, conflict validation, Codex launch mapping, and JSON response fields.
- Validation evidence:
  - `python -m unittest discover -s test -p 'test_runtime_py.py' -k 'launch_spec'`
  - `python -m unittest discover -s test -p 'test_cli_py.py' -k 'run_'`
