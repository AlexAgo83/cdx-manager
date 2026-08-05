## req_016_clarify_cdx_config_errors_for_unknown_sessions - Clarify cdx config errors for unknown sessions
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: CLI ergonomics
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-05

# Needs
- Operators who run `cdx config <name>` for a nonexistent session need an error that identifies the failed command and gives an immediate recovery path.

# Context
- `handle_config` resolves the requested session and currently raises only `Unknown session: <name>`.
- The same generic wording is used by other commands, but config has a direct discovery command: `cdx configs`, and session creation is performed by `cdx add`.
- Human and `--json` failures are rendered centrally from `CdxError`, so the clarified message must preserve the machine-readable unknown-session error code and normal nonzero exit behavior.

# Acceptance criteria
- AC1: `cdx config <missing-name>` returns a concise error that names the requested session and tells the user to run `cdx configs` to inspect existing sessions and `cdx add <name>` to create one when appropriate.
- AC2: `cdx config <missing-name> --json` preserves the standard JSON error envelope, `unknown_session` error code, and nonzero exit status while carrying the clarified actionable message.
- AC3: Usage errors such as missing or extra config names continue to show `Usage: cdx config <name> [--json]`, and successful config text/JSON responses are unchanged.
- AC4: The wording is documented or covered by command help/README where this repository’s CLI conventions require it, and focused tests assert text and JSON behavior.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_009_actionable_cdx_config_failures`
- Architecture decision(s): (none yet)

# References
- GitHub issue #3
- src/cli_commands.py::handle_config
- src/cli_args.py::_parse_config_args
- src/cli.py
- src/errors.py
- test/test_cli_py.py
- README.md

# AI Context
- Summary: Clarify cdx config errors for unknown sessions
- Keywords: request-chain-scaffold, clarify cdx config errors for unknown sessions, development-ready
- Use when: You need to implement or review the scaffolded workflow for Clarify cdx config errors for unknown sessions.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_036_improve_unknown_session_guidance_for_cdx_config`

# AC Traceability
- request-AC1 -> Task `task_027_orchestrate_actionable_cdx_config_error_guidance`. Proof: missing-session config errors name the target and mention `cdx configs` and `cdx add`.
- request-AC2 -> Task `task_027_orchestrate_actionable_cdx_config_error_guidance`. Proof: JSON failures preserve the standard error envelope and `unknown_session` code with actionable wording.
- request-AC3 -> Task `task_027_orchestrate_actionable_cdx_config_error_guidance`. Proof: usage-error and success paths remain covered and unchanged.
- request-AC4 -> Task `task_027_orchestrate_actionable_cdx_config_error_guidance`. Proof: focused tests and CLI documentation cover the updated config error wording.
