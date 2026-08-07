## item_055_extract_the_remaining_seven_command_domains - Extract the remaining seven command domains
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 100%
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

# Outcome

All nine domains extracted. `cli_commands.py` went 3313 -> 264 lines and now
defines nothing: 63 import statements, zero functions, zero constants. The 42
handlers stay importable from it and `_COMMAND_HANDLERS` is unchanged at 40
entries. 561 tests pass, `npm run lint` clean.

| commit | domain |
|---|---|
| `783fdee` | backup |
| `23c5818` | context & memory |
| `387f292` | the eight shared helpers -> `cli_helpers` |
| `a83eb36` | settings |
| `f9d5c81` | lifecycle |
| `a972e1d` | launch |
| `735476b` | auth |
| `d403570` | status |

Deviation from the plan: the shared helpers moved in one commit rather than
one at a time as each domain needed them. Eight relocations spread across five
extractions would have buried the moves inside unrelated diffs; as a single
commit the relocation reads on its own. After it, the five remaining domains
had zero shared helpers and extracted independently.

Three failure modes the pilot had not exposed, each caught by tests rather
than review:

- **Pass-through imports get stripped.** `_format_bytes` and `STATUS_USAGE`
  were imported by `cli_commands` for its own use and consumed by `cli.py`
  through the facade. Once the last in-file caller moved out, ruff removed
  them as unused and unrelated modules stopped importing. Both are now
  explicit `# noqa: F401` re-exports, and
  `test_cli_commands_facade_still_exposes_every_name_its_callers_import`
  fails if any future extraction drops one. Verified it fails when a
  re-export is removed.
- **Relative imports inside moved bodies.** Four function-local
  `from .cli_render import ...` statements in the status domain resolved one
  package level too shallow once inside `src/commands/`. Four tests failed;
  all such imports now re-level to `..`. status was the only domain with any.
- **ruff splits `X as X` re-exports.** isort emits one statement per
  redundant alias, which turned the facade into 50 separate imports. Grouped
  `# noqa: F401` blocks say the same thing in one place per module.

The extractions were driven by a script that cuts the named definitions
verbatim and derives the new module's imports from what the moved code
actually references. It refused to emit a module twice rather than guessing -
once on a nested function name, once on a function-local import - which is
what kept the moves verbatim.

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
