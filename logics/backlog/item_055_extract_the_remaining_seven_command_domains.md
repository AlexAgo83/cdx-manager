## item_055_extract_the_remaining_seven_command_domains - Extract the remaining seven command domains
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Maintainability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Seven domains remain in the file after the pilot: context and memory, status, auth, launch, session lifecycle, backup, and launch settings.
- Two helpers, `_resolve_confirmation` and `_bootstrap_claude_setup_token`, are used by more than one of them and cannot travel with any single domain.

# Scope
- In:
  - Extract the remaining domains, one commit each, in ascending order of coupling so the easiest land first.
  - Move `_resolve_confirmation` and `_bootstrap_claude_setup_token` into the shared helper layer, rather than duplicating them or leaving them in a module that no longer owns their callers.
  - Keep the facade complete after every extraction, so the import surface never regresses even mid-sequence.
  - Confirm at the end that `cli_commands` contains no handler of its own and reads as what it now is.
  - Run the full suite after each extraction.
- Out:
  - No behavior change or rename.
  - No test file split.
  - No new abstraction.
  - No re-litigating the domain grouping settled by the pilot.

# Acceptance criteria
- All nine domains live in their own modules and `cli_commands` defines no handler itself.
- The two cross-group helpers live in the shared helper layer, with a single definition each.
- Every import that worked before the request works after it.
- The full test suite passes after every individual extraction, not only at the end.
- No handler signature, name, or behavior differs from before the moves.
- The `_COMMAND_HANDLERS` dispatch dict is structurally unchanged.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: All nine domains live in their own modules and `cli_commands` defines no handler itself.
- request-AC2 -> This backlog slice. Proof: The two cross-group helpers live in the shared helper layer, with a single definition each.
- request-AC3 -> This backlog slice. Proof: Every import that worked before the request works after it.
- request-AC4 -> This backlog slice. Proof: The full test suite passes after every individual extraction, not only at the end.
- request-AC5 -> This backlog slice. Proof: No handler signature, name, or behavior differs from before the moves.
- request-AC8 -> This backlog slice. Proof: The `_COMMAND_HANDLERS` dispatch dict is structurally unchanged.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_015_navigable_command_modules`
- Architecture decision(s): (none yet)
- Request: `req_025_split_cli_commands_into_per_domain_command_modules_behind_a_facade`
- Primary task(s): `task_036_orchestrate_the_command_module_split`

# AI Context
- Summary: Extract the remaining seven command domains
- Keywords: scaffolded-backlog, extract the remaining seven command domains, implementation-ready
- Use when: Implementing the scaffolded slice for Extract the remaining seven command domains.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
