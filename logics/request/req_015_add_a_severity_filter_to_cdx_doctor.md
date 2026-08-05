## req_015_add_a_severity_filter_to_cdx_doctor - Add a severity filter to cdx doctor
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: CLI diagnostics
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-05

# Needs
- Operators need to focus `cdx doctor` output on one health severity when triaging warnings or failures.

# Context
- Health issues already carry canonical uppercase statuses `OK`, `WARN`, and `FAIL`.
- `handle_doctor` currently accepts only `--json` and renders the full report; filtering belongs after collection so diagnostics remain computed consistently.
- Both human and JSON consumers need the selected subset and a summary that agrees with what they receive.

# Acceptance criteria
- AC1: `cdx doctor --severity <OK|WARN|FAIL>` filters displayed issues to exactly that canonical severity; input is case-insensitive.
- AC2: The filter composes with `--json`; JSON retains the standard success envelope and returns a report whose issues and summary describe only the filtered subset, plus the normalized requested severity.
- AC3: Text output contains no issue rows outside the requested severity and reports a matching summary, including an empty-match result without error.
- AC4: Missing, repeated, or unsupported severity values fail with command usage that documents the three accepted values; existing `cdx doctor` and `cdx doctor --json` output stays backward compatible.
- AC5: Top-level help, command usage, and README document the option and focused tests cover every accepted severity, case normalization, empty matches, invalid input, text output, and JSON output.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_008_filterable_doctor_diagnostics`
- Architecture decision(s): (none yet)

# References
- GitHub issue #2
- src/cli_commands.py::handle_doctor
- src/health.py
- src/cli_args.py
- src/cli.py
- README.md
- test/test_cli_py.py

# AI Context
- Summary: Add a severity filter to cdx doctor
- Keywords: request-chain-scaffold, add a severity filter to cdx doctor, development-ready
- Use when: You need to implement or review the scaffolded workflow for Add a severity filter to cdx doctor.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_035_filter_cdx_doctor_report_by_severity`

# AC Traceability
- request-AC1 -> Task `task_026_orchestrate_cdx_doctor_severity_filtering`. Proof: severity parsing accepts canonical OK/WARN/FAIL values case-insensitively.
- request-AC2 -> Task `task_026_orchestrate_cdx_doctor_severity_filtering`. Proof: JSON output keeps the success envelope and reports filtered issues, summary, and normalized severity.
- request-AC3 -> Task `task_026_orchestrate_cdx_doctor_severity_filtering`. Proof: text output and summaries reflect only the requested severity, including empty matches.
- request-AC4 -> Task `task_026_orchestrate_cdx_doctor_severity_filtering`. Proof: invalid severity usage is rejected while unfiltered doctor output remains backward compatible.
- request-AC5 -> Task `task_026_orchestrate_cdx_doctor_severity_filtering`. Proof: help, README, and focused tests cover the accepted values, invalid input, text output, and JSON output.
