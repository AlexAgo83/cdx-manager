## item_038_make_cdx_run_validation_errors_specific_and_actionable - Make cdx run validation errors specific and actionable
> From version: 0.12.2
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `cdx run` currently collapses distinct argument validation failures into the same generic usage message.
- This makes JSON automation ambiguous and caused a caller to misread a rejected invocation as a successful run.
- The immediate bug is the named-session plus `--provider` conflict, but the same pattern affects several validation branches.

# Scope
- In:
  - Introduce condition-specific `CdxError` messages for known `cdx run` validation failures.
  - Keep `RUN_USAGE` as fallback guidance for unknown flags or parser-level usage failures.
  - Add focused tests for text and `--json` error behavior across the validation matrix.
  - Update user-facing docs if the command reference implies generic-only validation behavior.
- Out:
  - Changing valid `cdx run` execution semantics.
  - Adding new structured error codes unless required by the existing error model.
  - Redesigning argument parsing for commands other than `cdx run`.

# Acceptance criteria
- AC1: `cdx run main --cwd <path> --provider codex --prompt <text> --json` fails with `invalid_request` and a message equivalent to "cannot specify both a session name and --provider".
- AC2: Missing `--cwd` reports that `--cwd PATH` is required.
- AC3: Missing both `--prompt` and `--prompt-file` reports that one prompt source is required.
- AC4: Invalid `--kind` reports allowed values and the rejected value.
- AC5: `--reasoning-effort` and `--power` conflicts report the mutually exclusive options.
- AC6: Text output and JSON output use the same condition-specific message while preserving the existing JSON envelope shape.
- AC7: Unknown flags still show the complete usage contract.

# AC Traceability
- request-AC1 -> AC1, AC2, AC3, AC4, AC5. Proof: Known validation branches return condition-specific messages.
- request-AC2 -> AC1. Proof: Session plus provider conflict has an explicit mutual-exclusion message.
- request-AC3 -> AC2, AC3, AC4, AC5. Proof: Each listed validation condition is tested separately.
- request-AC4 -> AC7. Proof: Parser-level unknown input can keep full usage fallback.
- request-AC5 -> AC6. Proof: JSON envelope is preserved while message changes.
- request-AC6 -> AC7. Proof: Documentation/help remains aligned with accepted command usage.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_018_make_cdx_run_validation_errors_specific_and_actionable`
- Primary task(s): `task_029_make_cdx_run_validation_errors_specific_and_actionable`

# AI Context
- Summary: Implement condition-specific `cdx run` validation failures while preserving the JSON error contract.
- Keywords: GitHub issue #5, cdx run, RUN_USAGE, invalid_request, _parse_run_args, validation messages
- Use when: Working on CLI argument validation for `cdx run`.
- Skip when: The change is only about provider execution after validation succeeds.

# Priority
- Priority: High
- Rationale: Ambiguous validation errors mislead automation and can cause callers to report rejected runs as successful.

# Notes
- Hybrid rationale: Derived from request `req_018_make_cdx_run_validation_errors_specific_and_actionable` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_018_make_cdx_run_validation_errors_specific_and_actionable.md`.
- Generated locally by logics-manager.
- Related existing corpus is Done and broader: `item_003_command_ergonomics_validation_and_safety`, `task_000_command_ergonomics_validation_and_safety`.

# Tasks
- `task_029_make_cdx_run_validation_errors_specific_and_actionable`
