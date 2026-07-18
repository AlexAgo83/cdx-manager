## item_027_deduplication_dead_code_removal_and_docs_hygiene - Deduplication, dead-code removal, and docs hygiene
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Three drifting update-warning builders, two _format_bytes, two near-identical progress factories, duplicated status_source regexes; dead code (_update_notice_warning, claude_refresh asyncio branch, shutil_which); .gitignore/README/help/usage drift.

# Scope
- In:
  - Keep one update-warning builder in cli_helpers and import it from cli.py and cli_view.py.
  - Keep the None-safe _format_bytes; migrate the other call sites.
  - Merge the two progress factories into one with an optional prefix handler.
  - Extract the status_source limit regexes into one module constant used by both parse paths.
  - Delete _update_notice_warning, the claude_refresh asyncio branch (and its only-async test), and shutil_which (call shutil.which directly).
  - Remove dead .gitignore entries for tracked logics.yaml/LOGICS.md; fix the README Python 3.9 note; add --kind to cdx run --help; parameterize _parse_history_period so cdx stats prints its own usage.
- Out:
  - Any behavior change beyond the unified helpers' existing semantics.

# Acceptance criteria
- One implementation each for the update-warning builder, byte formatter, progress factory, and limit regexes; grep finds no duplicate.
- Deleted symbols have no remaining references; full suite green.
- cdx stats argument errors print stats usage; cdx run --help lists --kind.

# Report
- Update-warning payload generation is centralized through `cli_helpers`.
- Disk byte formatting now uses the shared None-safe helper.
- Status and notify progress callbacks share one session-progress factory.
- Codex limit percentage regexes are declared once and reused by both parse paths.
- Removed the unused `_update_notice_warning`, Claude async refresh branch, and `notify.shutil_which` wrapper.
- Cleaned stale `.gitignore` entries and the stale README Python-floor note; top-level help now lists `cdx run --kind`.
- Validation: `python3 -m unittest discover -s test -p 'test_cli_py.py'`; `python3 -m unittest discover -s test -p 'test_notify_py.py'`; `python3 -m unittest discover -s test -p 'test_runtime_py.py'`; `python3 -m unittest discover -s test -p 'test_status_source_py.py'`; `python3 scripts/verify_project_docs.py`; `logics-manager lint --require-status`.

# AC Traceability
- request-AC12 -> This backlog slice. Proof: One implementation each for the update-warning builder, byte formatter, progress factory, and limit regexes; grep finds no duplicate.
- request-AC13 -> This backlog slice. Proof: Deleted symbols have no remaining references; full suite green.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Primary task(s): `task_021_orchestrate_july_2026_code_review_remediation`

# AI Context
- Summary: Deduplication, dead-code removal, and docs hygiene
- Keywords: scaffolded-backlog, deduplication, dead-code removal, and docs hygiene, implementation-ready
- Use when: Implementing the scaffolded slice for Deduplication, dead-code removal, and docs hygiene.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Low
- Rationale: Set by scaffold input or defaulted for grooming.
