## task_029_make_cdx_run_validation_errors_specific_and_actionable - Make cdx run validation errors specific and actionable
> From version: 0.12.2
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_038_make_cdx_run_validation_errors_specific_and_actionable`

# Acceptance criteria
- AC1: `cdx run main --cwd <path> --provider codex --prompt <text> --json` fails with `invalid_request` and a message equivalent to "cannot specify both a session name and --provider".
- AC2: Missing `--cwd` reports that `--cwd PATH` is required.
- AC3: Missing both `--prompt` and `--prompt-file` reports that one prompt source is required.
- AC4: Invalid `--kind` reports allowed values and the rejected value.
- AC5: `--reasoning-effort` and `--power` conflicts report the mutually exclusive options.
- AC6: Text output and JSON output use the same condition-specific message while preserving the existing JSON envelope shape.
- AC7: Unknown flags still show the complete usage contract.

# Plan
- [ ] 1. Inventory every `raise CdxError(RUN_USAGE)` path in `_parse_run_args` and any equivalent `cdx run` checks.
- [ ] 2. Replace known validation branches with concise condition-specific messages.
- [ ] 3. Preserve full `RUN_USAGE` for unknown flags and parser-level fallback cases.
- [ ] 4. Add unit tests for parser messages and command-level JSON envelopes for each acceptance criterion.
- [ ] 5. Update README/help text only if exposed examples or troubleshooting text become stale.
- [ ] 6. Run focused CLI argument tests, focused `cdx run --json` error tests, and Logics lint.

# Validation
- Planned: focused CLI argument parser and `cdx run --json` error tests.
- Planned: `logics-manager lint --require-status`.
- Finish workflow executed on 2026-08-05.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-05.
- Linked backlog item(s): `item_038_make_cdx_run_validation_errors_specific_and_actionable`
- Related request(s): `req_018_make_cdx_run_validation_errors_specific_and_actionable`

# AI Context
- Summary: Implement actionable `cdx run` validation errors for issue #5.
- Keywords: GitHub issue #5, cdx run, RUN_USAGE, invalid_request, _parse_run_args, JSON error envelope
- Use when: Implementing the `cdx run` argument validation grooming slice.
- Skip when: Work is about post-launch run registry failures or release checksum automation.

# Links
- Request: `req_018_make_cdx_run_validation_errors_specific_and_actionable`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# AC Traceability
- request-AC1 -> Task AC1, Task AC2, Task AC3, Task AC4, Task AC5. Proof: Known validation branches get distinct messages.
- request-AC2 -> Task AC1. Proof: Session plus provider conflict is explicit.
- request-AC3 -> Task AC2, Task AC3, Task AC4, Task AC5. Proof: Listed validation failures have separate tests.
- request-AC4 -> Task AC7. Proof: Unknown flags keep full usage fallback.
- request-AC5 -> Task AC6. Proof: JSON envelope compatibility remains tested.
- request-AC6 -> Task plan step 5. Proof: Documentation/help is checked for stale guidance.
