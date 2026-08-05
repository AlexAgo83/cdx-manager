## item_035_filter_cdx_doctor_report_by_severity - Filter cdx doctor report by severity
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: CLI diagnostics
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Full doctor output obscures the class of issue an operator is actively resolving.
- No parser or rendering contract exists for severity-scoped reports.

# Scope
- In:
  - Parse one optional severity flag with normalized validation.
  - Filter the collected report without changing collection.
  - Recompute the displayed summary from filtered issues and expose selected severity in JSON.
  - Document and test the new CLI contract.
- Out:
  - New health checks, severity reclassification, multi-value/negated filters, and repair behavior.

# Acceptance criteria
- AC1: Exactly one case-insensitive `--severity` value is accepted from OK, WARN, FAIL.
- AC2: Filtered text/JSON reports contain only matching issues and matching counts.
- AC3: Unfiltered output remains byte/shape compatible apart from intentional help documentation.
- AC4: Invalid argument forms are regression-tested.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Exactly one case-insensitive `--severity` value is accepted from OK, WARN, FAIL.
- request-AC2 -> This backlog slice. Proof: AC2: Filtered text/JSON reports contain only matching issues and matching counts.
- request-AC3 -> This backlog slice. Proof: AC3: Unfiltered output remains byte/shape compatible apart from intentional help documentation.
- request-AC4 -> This backlog slice. Proof: AC4: Invalid argument forms are regression-tested.
- request-AC5 -> This backlog slice. Proof: AC4: Invalid argument forms are regression-tested.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_008_filterable_doctor_diagnostics`
- Architecture decision(s): (none yet)
- Request: `req_015_add_a_severity_filter_to_cdx_doctor`
- Primary task(s): `task_026_orchestrate_cdx_doctor_severity_filtering`

# AI Context
- Summary: Filter cdx doctor report by severity
- Keywords: scaffolded-backlog, filter cdx doctor report by severity, implementation-ready
- Use when: Implementing the scaffolded slice for Filter cdx doctor report by severity.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Notes
- Task `task_026_orchestrate_cdx_doctor_severity_filtering` was finished via `logics-manager flow finish task` on 2026-08-05.
