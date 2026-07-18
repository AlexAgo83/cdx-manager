## item_025_unify_npm_entrypoint_through_cli_entry - Unify npm entrypoint through cli_entry
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
- bin/cdx calls main() directly, duplicating cli_entry error handling and skipping Windows ANSI/encoding setup, so npm-installed Windows users get garbled output while pip users do not.

# Scope
- In:
  - bin/cdx invokes cli_entry(); delete the duplicated error handling in the launcher.
  - Regression test asserting the npm launcher path routes through cli_entry.
- Out:
  - Changes to the pip console-script wiring.

# Acceptance criteria
- npm and pip entrypoints execute the same setup and error-handling path.
- bin/cdx contains no duplicated error-handling logic.

# Report
- `bin/cdx` now delegates directly to `src.cli.cli_entry()`, reusing Windows ANSI/encoding setup and centralized error handling.
- Regression coverage asserts the launcher imports `cli_entry` and no longer carries duplicated error handling.
- Validation: `python3 -m unittest discover -s test -p 'test_cli_py.py' -k bin_cdx`.

# AC Traceability
- request-AC10 -> This backlog slice. Proof: npm and pip entrypoints execute the same setup and error-handling path.
- request-AC14 -> This backlog slice. Proof: bin/cdx contains no duplicated error-handling logic.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_003_code_review_remediation_wave_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_010_address_july_2026_code_review_findings_data_safety_reliability_and_cleanup`
- Primary task(s): `task_021_orchestrate_july_2026_code_review_remediation`

# AI Context
- Summary: Unify npm entrypoint through cli_entry
- Keywords: scaffolded-backlog, unify npm entrypoint through cli_entry, implementation-ready
- Use when: Implementing the scaffolded slice for Unify npm entrypoint through cli_entry.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
