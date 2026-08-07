## item_054_pilot_the_split_with_the_runs_and_maintenance_domains - Pilot the split with the runs and maintenance domains
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
- The measurement says the domains are independent, but a measurement is not an extraction. Whether the facade keeps every import working, and whether a domain's helpers really come away cleanly, is only known by doing it.
- Committing to all nine extractions before proving the pattern risks discovering the problem on the eighth.

# Scope
- In:
  - Create the package for command modules and extract the runs domain first: run, runs, run-status, run-report, run-tail, select, schema, with the helpers used only by them.
  - Turn `cli_commands` into a facade re-exporting the extracted handlers, following the `__all__` convention `src/cli.py` already documents, so existing imports keep working.
  - Extract the maintenance domain second: doctor, repair, clean, disk, update.
  - Move only. Do not rename, resequence, or rewrite anything in the same commit as an extraction, so the diff reads as a move and `git log --follow` stays useful.
  - Run the full suite after each extraction, not once at the end.
  - Record what the pilot cost and whether the helper attribution held, so the decision to continue is made on evidence rather than on the original estimate.
- Out:
  - No extraction of the remaining seven domains in this slice.
  - No test file split yet.
  - No relocation of the two shared helpers yet; the pilot domains do not use them.
  - No new abstraction.

# Acceptance criteria
- Every handler in the runs and maintenance domains lives in its own module, with the helpers used only by that domain alongside it.
- `from src.cli_commands import <handler>` works for every handler that worked before, including the ones now defined elsewhere.
- `src/cli.py` and `test/test_cli_py.py` are unchanged by the extraction, aside from anything the facade genuinely cannot cover.
- The full test suite passes after each of the two extractions independently.
- No handler signature, name, or behavior differs from before the move.
- The pilot's outcome is recorded, including any helper that did not move as cleanly as measured.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Every handler in the runs and maintenance domains lives in its own module, with the helpers used only by that domain alongside it.
- request-AC2 -> This backlog slice. Proof: `from src.cli_commands import <handler>` works for every handler that worked before, including the ones now defined elsewhere.
- request-AC4 -> This backlog slice. Proof: `src/cli.py` and `test/test_cli_py.py` are unchanged by the extraction, aside from anything the facade genuinely cannot cover.
- request-AC5 -> This backlog slice. Proof: The full test suite passes after each of the two extractions independently.
- request-AC6 -> This backlog slice. Proof: No handler signature, name, or behavior differs from before the move.
- request-AC8 -> This backlog slice. Proof: The pilot's outcome is recorded, including any helper that did not move as cleanly as measured.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_015_navigable_command_modules`
- Architecture decision(s): (none yet)
- Request: `req_025_split_cli_commands_into_per_domain_command_modules_behind_a_facade`
- Primary task(s): `task_036_orchestrate_the_command_module_split`

# AI Context
- Summary: Pilot the split with the runs and maintenance domains
- Keywords: scaffolded-backlog, pilot the split with the runs and maintenance domains, implementation-ready
- Use when: Implementing the scaffolded slice for Pilot the split with the runs and maintenance domains.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
