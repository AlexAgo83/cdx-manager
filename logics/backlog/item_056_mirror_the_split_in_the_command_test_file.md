## item_056_mirror_the_split_in_the_command_test_file - Mirror the split in the command test file
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
- `test/test_cli_py.py` is 7116 lines, larger than the module it tests, and covers all nine domains plus health, ranking, schema, and version concerns.
- Its structure follows the source, so splitting it before the source has settled would mean splitting it twice.

# Scope
- In:
  - Split the test file to mirror the module structure the source split produced, one test module per command domain.
  - Move shared fixtures and helpers into a common test helper module rather than duplicating them across the new files.
  - Keep every existing test, unchanged in content: this is a move, and a test that changes while moving is a test whose regression cannot be attributed.
  - Verify the total test count is identical before and after, so nothing is silently dropped by a bad move.
  - Give the tests that are not about a single command domain (ranking, schema, version agreement, health) a home that says so, rather than leaving them wherever they happen to sit.
- Out:
  - No new tests in this slice.
  - No rewriting or deduplicating of existing assertions.
  - No change to the source modules.

# Acceptance criteria
- Each command domain has its own test module, matching the source module names.
- The number of tests collected is identical before and after the split.
- Shared fixtures live in one place and are imported, not copied.
- No test body differs from before the move.
- Tests not tied to one command domain are in a module named for what they cover.
- The full suite passes and coverage totals do not drop.

# AC Traceability
- request-AC7 -> This backlog slice. Proof: Each command domain has its own test module, matching the source module names.
- request-AC4 -> This backlog slice. Proof: The number of tests collected is identical before and after the split.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_015_navigable_command_modules`
- Architecture decision(s): (none yet)
- Request: `req_025_split_cli_commands_into_per_domain_command_modules_behind_a_facade`
- Primary task(s): `task_036_orchestrate_the_command_module_split`

# AI Context
- Summary: Mirror the split in the command test file
- Keywords: scaffolded-backlog, mirror the split in the command test file, implementation-ready
- Use when: Implementing the scaffolded slice for Mirror the split in the command test file.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
