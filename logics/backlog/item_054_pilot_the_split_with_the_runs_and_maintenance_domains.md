## item_054_pilot_the_split_with_the_runs_and_maintenance_domains - Pilot the split with the runs and maintenance domains
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

# Pilot outcome

The pattern holds. Both extractions landed with 560 tests passing after each,
`src/cli.py` untouched, and `cli_commands` shrinking 3313 -> 2126 lines.
Commits: `3e42788` (runs), `3429fc3` (maintenance).

Three things did not match the estimate the plan was built on:

- **Nine shared helpers, not two.** The original measurement counted direct
  handler -> helper calls. Extraction needs the transitive closure, because a
  helper reached only through another helper still has to move. Re-measured:
  62 of 71 helpers are exclusive to one domain, 9 are shared, none are
  unreachable. The split is still cheap; the "2" was an artifact of the
  measurement, not a property of the code.
- **The pilot domains did use a shared helper.** This slice scoped out moving
  them on the premise that they did not. `handle_clean` shares
  `_resolve_confirmation` with the auth and lifecycle domains, so it moved to
  `cli_helpers` during the pilot rather than in wave 2.
- **The facade cannot cover module-attribute patching.** Two
  `mock.patch("src.cli_commands.shutil.rmtree" / ".os.remove")` targets in
  `test_cli_py.py` reach through the module globals, which a re-export does
  not rebind; once ruff removed the now-unused `import shutil`, the target
  stopped resolving. Both were repointed at `src.commands.maintenance`. This
  is the AC exception clause, and it is the only place the facade fell short.

Two packaging globs also missed the new package: `py_compile` in both
`package.json` and `.github/workflows/ci.yml` matched only `src/*.py`, so
`src/commands/` would have gone un-byte-compiled in CI. Both now include it.
The npm `files` list already recursed correctly.

Implication for wave 2: extract each domain against the transitive closure,
and expect the remaining 8 shared helpers to need relocation as the first
domain that uses each one is extracted.

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
