## task_010_implement_cdx_run_usage_extraction_and_launcher_payload - Implement cdx run usage extraction and launcher payload
> From version: 0.7.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Headless automation
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Derived from backlog item `item_010_populate_cdx_run_usage_and_launcher_payload`.
- Related request: `req_001_populate_headless_run_usage_tokens_for_orchestia`.
- This task depends on stable provider artifacts from `item_011_use_provider_native_headless_launch_modes_for_cdx_run` or equivalent verified provider fixtures.
- The goal is additive: identify cdx-manager responses with `launcher: "cdx"` and populate nullable usage fields when trusted provider output exposes token counts.

```mermaid
%% logics-kind: task
%% logics-signature: task|implement-cdx-run-usage-extraction-and-l|item-010-populate-cdx-run-usage-and-laun|1-add-top-level-launcher-cdx-to|python-m-py-compile-bin-cdx-src
stateDiagram-v2
    state "item_010 usage and launcher payload" as Backlog
    state "1. Add launcher field" as Launcher
    state "2. Add run_usage parser" as Parser
    state "3. Cover Claude and Codex fixtures" as Fixtures
    state "4. Wire result payload" as Payload
    state "5. Validate compatibility" as Validate
    [*] --> Backlog
    Backlog --> Launcher
    Launcher --> Parser
    Parser --> Fixtures
    Fixtures --> Payload
    Payload --> Validate
    Validate --> [*]
```

# Plan
- [x] 1. Add top-level `launcher: "cdx"` to `cdx run --json` result envelopes without removing or renaming existing fields.
- [x] 2. Add a small `run_usage` module that returns the existing all-null usage payload by default.
- [x] 3. Implement provider-aware parsing for verified Claude JSON or JSONL usage shapes, with explicit cumulative-vs-delta fixture expectations.
- [x] 4. Implement provider-aware parsing for verified Codex `exec --json` or JSONL usage shapes only after fixture evidence exists.
- [x] 5. Reject or ignore unknown output shapes and broad human-text token strings by returning all-null usage.
- [x] 6. Wire extracted usage into `_run_result_payload` using the captured stdout artifact path and selected provider.
- [x] 7. Add focused `unittest` coverage for missing files, unknown providers, malformed output, Claude fixtures, Codex fixtures, and all-null fallback.
- [x] 8. Add a CLI-level test that simulates a provider writing usage to stdout and verifies `launcher`, `usage`, artifact paths, and backward-compatible fields in the final cdx JSON.
- [x] 9. Update linked Logics docs with final provider fixture notes and validation evidence.
- [x] CHECKPOINT: leave the wave commit-ready and update linked Logics docs before continuing.
- [x] GATE: do not close a wave or step until the relevant automated tests and quality checks have been run successfully.

# Backlog
- `item_010_populate_cdx_run_usage_and_launcher_payload`

# Definition of Done (DoD)
- [x] Code is implemented and reviewed.
- [x] Validation passes.
- [x] Linked docs are synchronized.

# Validation
- `python -m py_compile bin/cdx src/*.py test/test_*_py.py`
- `python -m unittest discover -s test -p 'test_*_py.py'`
- `npm run lint`
- `npm test`
- `python3 -m logics_manager lint --require-status`

# AC Traceability
- AC1 -> Plan: top-level launcher field. Proof: `launcher: "cdx"` payload assertions.
- AC2 -> Plan: verified provider usage parsing. Proof: `src/run_usage.py` parser tests.
- AC3 -> Plan: all-null fallback behavior. Proof: missing, malformed, unsupported, and unknown-output tests.
- AC4 -> Plan: Claude fixture coverage. Proof: Claude JSON/JSONL fixture tests.
- AC5 -> Plan: Codex fixture coverage. Proof: Codex `exec --json` fixture tests.
- AC6 -> Plan: conservative parser boundaries. Proof: no free-text token parsing in `src/run_usage.py`.
- AC7 -> Plan: unittest and CLI integration coverage. Proof: `test_runtime_py.py` and `test_cli_py.py` focused runs.
- AC8 -> Plan: additive payload compatibility. Proof: existing artifact paths and result fields remain asserted.
- AC9 -> Plan: avoid selection string changes. Proof: no `cdx select` reason text changes in this slice.
- AC10 -> Plan: provider-native headless modes coordinated through `item_011`. Proof: provider stdout/stderr captured as artifacts.

# Report
- Implemented `src/run_usage.py` with conservative Codex/Claude JSON and JSONL usage extraction, unknown-format null fallback, and no free-text token parsing.
- Added top-level `launcher: "cdx"` to `cdx run --json` result payloads.
- Validation evidence:
  - `python -m unittest discover -s test -p 'test_runtime_py.py'`
  - `python -m unittest discover -s test -p 'test_cli_py.py' -k 'run_'`
  - `npm run lint`

# AI Context
- Summary: Implement the additive `launcher` field and conservative token usage extraction for `cdx run --json`.
- Keywords: run_usage, usage tokens, launcher, cdx run json, Claude JSONL, Codex JSONL, unittest
- Use when: Implementing or reviewing payload-level usage extraction for Orchestia.
- Skip when: The provider-native headless launch modes are still missing or fixture output is unavailable.

# Links
- Request: `req_001_populate_headless_run_usage_tokens_for_orchestia`
- Product brief(s): `prod_002_headless_automation_contract_for_orchestia`
- Architecture decision(s): `adr_002_provider_native_headless_run_boundary`
