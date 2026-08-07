## item_043_replace_catch_all_usage_errors_with_specific_machine_readable_error_codes - Replace catch-all usage errors with specific machine-readable error codes
> From version: 0.12.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `run_cdx_error_code()` in `src/run_command.py:17` classifies errors by string-prefix matching the exception message, so every distinct argument mistake that raises `RUN_USAGE` collapses to the single code `invalid_request`.
- The resulting payload has every descriptive field null and carries the full human usage line as its message, which tells an automated caller nothing about which argument was wrong.
- This has produced a real silent false positive: a caller passing a session name together with `--provider` received that all-null payload and treated the failed launch as successful, because no field distinguished it from any other usage error.

# Scope
- In:
  - Enumerate the distinct argument-failure classes `cdx run` can produce, minimally: mutually exclusive arguments, missing required argument, unknown value for a constrained option, and out-of-range numeric value.
  - Introduce a structured argument error carrying a specific code and the offending argument names, raised at the point of detection in `src/cli_args.py` rather than reconstructed later from message text.
  - Extend the failure payload so the offending argument names are present as data, not only inside the human message.
  - Keep the human-readable usage message in the payload for terminal users, and keep the existing exit codes.
  - Retire message-prefix sniffing for the cases now carrying an explicit code, keeping the fallback only for errors not yet classified.
  - Apply the same treatment to the other subcommands wrapped by programmatic callers where the same catch-all currently applies.
  - Add tests asserting the specific code and the reported argument names for each failure class, including the session-plus-provider case.
- Out:
  - No renaming of existing non-usage error codes such as `invalid_cwd` or `session_disabled`.
  - No change to exit codes.
  - No localization of error messages.

# Acceptance criteria
- Given `cdx run <session> --provider <provider> --cwd <path> --prompt <text> --json`, the payload reports a mutually-exclusive-arguments error code and names both offending arguments as data.
- Given a `cdx run` invocation missing `--cwd`, the payload reports a missing-required-argument code naming that argument, distinguishable from the mutually-exclusive case by code alone.
- Given an unsupported `--permission` value, the payload reports an invalid-value code naming the argument, and lists the accepted values.
- Given `--timeout-seconds` outside the accepted range, the payload reports an out-of-range code naming that argument.
- Given any of the above, the human-readable usage message remains present in the payload and the exit code is unchanged from current behavior.
- No error classification for the above cases depends on matching the prefix of a message string.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: Given `cdx run <session> --provider <provider> --cwd <path> --prompt <text> --json`, the payload reports a mutually-exclusive-arguments error code and names both offending arguments as data.
- request-AC8 -> This backlog slice. Proof: Given a `cdx run` invocation missing `--cwd`, the payload reports a missing-required-argument code naming that argument, distinguishable from the mutually-exclusive case by code alone.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Primary task(s): `task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers`

# AI Context
- Summary: Replace catch-all usage errors with specific machine-readable error codes
- Keywords: scaffolded-backlog, replace catch-all usage errors with specific machine-readable error codes, implementation-ready
- Use when: Implementing the scaffolded slice for Replace catch-all usage errors with specific machine-readable error codes.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
