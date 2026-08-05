## req_018_make_cdx_run_validation_errors_specific_and_actionable - Make cdx run validation errors specific and actionable
> From version: 0.12.2
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: CLI ergonomics
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- `cdx run` callers need validation failures to explain the exact invalid condition instead of receiving the generic `RUN_USAGE` string for every error.
- Automation using `--json` must be able to distinguish missing inputs, incompatible options, and invalid values without scraping a usage dump.
- Human operators should get a short actionable message first, with usage remaining available as fallback guidance.

# Context
- GitHub issue #5 reports that `_parse_run_args` currently raises the same generic usage message for missing `--cwd`, missing prompt input, invalid `--kind`, `--reasoning-effort`/`--power` mismatch, and mutually exclusive session plus `--provider`.
- The observed 2026-08-05 failure was `cdx run main --cwd ... --provider codex ...`, where a named session and explicit provider are mutually exclusive.
- The JSON response used `invalid_request` but all identifying fields were null and the message did not identify the actual mutual-exclusion violation.
- Existing broad CLI ergonomics coverage exists in `item_003_command_ergonomics_validation_and_safety` and `task_000_command_ergonomics_validation_and_safety`, but those docs are Done and do not enumerate the current `cdx run` validation matrix.

# Acceptance criteria
- AC1: Every known `_parse_run_args` validation branch returns a specific message naming the failed condition.
- AC2: Passing both a session name and `--provider` returns an actionable mutual-exclusion message in text and JSON modes.
- AC3: Missing `--cwd`, missing both `--prompt` and `--prompt-file`, invalid `--kind`, and invalid `--reasoning-effort`/`--power` combinations each have distinct tests and distinct messages.
- AC4: Unknown flags and genuinely unparseable input may still fall back to the full `RUN_USAGE` text.
- AC5: The JSON error envelope remains backward compatible for `ok`, `session`, `cwd`, `run_id`, and `error.code`, while `error.message` becomes condition-specific.
- AC6: Help and README examples remain accurate for `cdx run`.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- GitHub issue #5
- `src/cli_args.py::_parse_run_args`
- `src/cli_args.py::RUN_USAGE`
- `src/cli_commands.py::handle_run`
- `src/errors.py`
- `test/test_cli_args_py.py`
- `test/test_cli_py.py`
- Existing broad corpus: `item_003_command_ergonomics_validation_and_safety`, `task_000_command_ergonomics_validation_and_safety`

# AI Context
- Summary: Replace generic `cdx run` validation usage failures with condition-specific actionable messages.
- Keywords: GitHub issue #5, cdx run, RUN_USAGE, _parse_run_args, invalid_request, session provider mutual exclusion
- Use when: Implementing or reviewing `cdx run` argument validation and JSON error behavior.
- Skip when: The work is about runtime provider failures after argument validation has already passed.

# Backlog
- none
- `item_038_make_cdx_run_validation_errors_specific_and_actionable`
