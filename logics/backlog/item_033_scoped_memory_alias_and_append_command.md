## item_033_scoped_memory_alias_and_append_command - Scoped memory alias and append command
> From version: 0.11.2
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `cdx context` is technically accurate but not obvious to users asking where durable project memory lives.
- Current workspace inference is not enough when the user wants to append to global memory or to a named project from another repo.
- `cdx context set` replaces the whole file, so a quick one-line decision note is more dangerous than it needs to be.
- Provider-private memory files exist under profiles, but using them would be brittle, opaque, and outside the stable `cdx-manager` contract.

# Scope
- In:
  - Add `append_context(base_dir, note, cwd=None)` or equivalent in `src/context_store.py` using the existing path and atomic write helpers.
  - Add the smallest scope resolver needed for `current`, `global`, and `project` memory. Prefer path resolution when `--project` points at an existing path; otherwise map the project name to a stable local context path and store enough metadata to explain it in JSON/path output.
  - Add `append` handling to the existing context command or shared helper so `cdx context append <text...>` can be supported if it falls out naturally with little code.
  - Add `cdx memory [--global|--project <name-or-path>] [view|show|path|init|edit|clear|set|append] [text...] [--json]` as a thin wrapper over the same implementation; `cdx memory` should default to current-workspace view/show.
  - Validate that `--global` and `--project` are not combined, that `--project` is not empty, and that append text is not empty after trimming.
  - Return concise text output and parseable JSON for memory actions, with action names such as `memory.view`, `memory.set`, and `memory.append`, plus scope metadata.
  - Update top-level help, short command help, README command table, data layout notes, and shared handoff documentation where needed.
  - Add focused unit tests in `test/test_context_store_py.py` and `test/test_cli_py.py`.
- Out:
  - New persistent storage outside `contexts/<workspace-hash>/context.md`.
  - Direct access to `profiles/*/memories_*.sqlite` or any other provider-owned database.
  - Automatic summarization, compression, or transcript mining.
  - Multi-workspace memory browsing, project listing, global memory aggregation, or cross-machine sync.
  - Permissions, ACLs, encryption, or remote APIs beyond the existing local file behavior.

# Acceptance criteria
- `cdx memory` and `cdx memory view` show the same content as `cdx context show` for the current workspace.
- `cdx memory --global append "Remember: prefer RTK for noisy commands"` writes to a global memory file and does not modify the current workspace memory.
- `cdx memory --project A append "Decision: ship the lazy version"` writes to project `A` memory and can be run from a different cwd.
- `cdx memory --project /path/to/repo path --json` resolves an existing path to the same workspace hash that would be used when running inside that repo.
- `cdx memory path|init|edit|clear|set` reuse existing context behavior for the selected scope and support `--json` consistently.
- `cdx memory append "Decision: keep cdx-manager as a launcher"` preserves previous content and adds the note at the end with a readable newline boundary.
- Appending to a missing memory creates the selected memory file and writes only the appended note plus a trailing newline unless the implementation deliberately initializes the template first and tests that behavior.
- Whitespace-only append input, empty `--project`, and combined `--global --project` fail with `CdxError` and do not create or modify memory files.
- `cdx context` behavior and existing context/handoff tests continue to pass unchanged.
- Documentation tells users to use `cdx memory` for explicit current/global/project memory and warns that provider-private memory files are not the supported interface.
- The implementation passes the focused context/CLI tests and the Logics validation commands.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: `cdx memory` and `cdx memory view` show the same content as `cdx context show` for the current workspace.
- request-AC2 -> This backlog slice. Proof: `cdx memory --global append "Remember: prefer RTK for noisy commands"` writes to a global memory file and does not modify the current workspace memory.
- request-AC3 -> This backlog slice. Proof: `cdx memory --project A append "Decision: ship the lazy version"` writes to project `A` memory and can be run from a different cwd.
- request-AC4 -> This backlog slice. Proof: `cdx memory --project /path/to/repo path --json` resolves an existing path to the same workspace hash that would be used when running inside that repo.
- request-AC5 -> This backlog slice. Proof: `cdx memory path|init|edit|clear|set` reuse existing context behavior for the selected scope and support `--json` consistently.
- request-AC6 -> This backlog slice. Proof: `cdx memory append "Decision: keep cdx-manager as a launcher"` preserves previous content and adds the note at the end with a readable newline boundary.
- request-AC7 -> This backlog slice. Proof: Appending to a missing memory creates the selected memory file and writes only the appended note plus a trailing newline unless the implementation deliberately initializes the template first and tests that behavior.
- request-AC8 -> This backlog slice. Proof: Whitespace-only append input, empty `--project`, and combined `--global --project` fail with `CdxError` and do not create or modify memory files.
- request-AC9 -> This backlog slice. Proof: `cdx context` behavior and existing context/handoff tests continue to pass unchanged.
- request-AC10 -> This backlog slice. Proof: Documentation tells users to use `cdx memory` for explicit current/global/project memory and warns that provider-private memory files are not the supported interface.
- request-AC11 -> This backlog slice. Proof: The implementation passes the focused context/CLI tests and the Logics validation commands.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_006_workspace_memory_command_for_cdx`
- Architecture decision(s): (none yet)
- Request: `req_013_add_a_small_workspace_memory_command_to_cdx`
- Primary task(s): `task_024_orchestrate_workspace_memory_command`

# AI Context
- Summary: Scoped memory alias and append command
- Keywords: scaffolded-backlog, scoped memory alias and append command, implementation-ready
- Use when: Implementing the scaffolded slice for Scoped memory alias and append command.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
