## req_013_add_a_small_workspace_memory_command_to_cdx - Add a small workspace memory command to cdx
> From version: 0.11.2
> Schema version: 1.0
> Status: Done
> Understanding: 100
> Confidence: 95
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- Users already have a per-workspace shared context file, but the `cdx context` name is implementation-oriented and does not clearly communicate that this is the durable project memory shared between assistant sessions.
- Users need memory at two scopes: a global operator memory that follows them everywhere, and project/repo memory that can be selected explicitly instead of only inferred from the current working directory.
- Users need a fast way to add one decision, warning, command, or project note without replacing the whole context file.
- Users need a simple way to list the memory scopes `cdx` knows how to address, especially global memory and named project memories, without scanning the filesystem or discovering repositories.
- The feature should reuse the existing `~/.cdx/contexts/<workspace-hash>/context.md` store and handoff behavior instead of creating another memory database or touching provider-private memory files.

# Context
- `src/context_store.py` already owns stable workspace hashing, `context.md` path resolution, read, write, init, clear, edit, and install-to-session behavior.
- `src/cli_commands.py::handle_context` already exposes `cdx context show|path|init|edit|clear|set [text...] [--json]` and `cdx handoff` already installs the same context as `shared-context.md` into a target provider profile.
- The current context API accepts `cwd`, so a project selector can stay small by resolving the memory scope before calling the existing store helpers.
- Codex profiles may contain provider-owned SQLite files such as `memories_1.sqlite`; this request must not inspect, mutate, merge, or depend on those internal files.
- Recent Codex releases added stronger local memory/import signals, including migration from Claude Code project memory and related project settings. `cdx memory` should keep its storage explicit and user-controlled so a later import/export bridge can target it without coupling to Codex internals.
- Recent Claude Code releases document project auto memory under `~/.claude/projects/<project>/memory/`, `MEMORY.md`, and `/memory`, plus global/project instruction files. This request should treat those as provider-owned sources for possible future sync/export, not as the primary `cdx` memory store.
- Recent Claude Code and Codex changes also expose richer model, effort, headless JSON, subagent, and MCP diagnostics. Those are useful follow-ups for `cdx doctor`, `cdx status`, and `cdx run --json`, but they should not block the first memory command.
- The smallest useful product surface is a friendly `cdx memory` alias over the existing context store plus one new append operation.

# Acceptance criteria
- AC1: A user can run `cdx memory` or `cdx memory view` to display the current workspace memory from the same `context.md` file used by `cdx context show`.
- AC2: A user can run `cdx memory --global view|set|append|path|init|edit|clear` to manage one global memory file that is independent of the current repo.
- AC3: A user can run `cdx memory --project <name-or-path> view|set|append|path|init|edit|clear` to manage a named or path-resolved project memory even when the shell is in another directory.
- AC4: `--global` and `--project` are mutually exclusive; without either flag, `cdx memory` targets the current workspace/repo.
- AC5: A user can run `cdx memory path`, `init`, `edit`, `clear`, and `set` with behavior matching the existing `cdx context` subcommands for the selected scope, including `--json` support.
- AC6: A user can run `cdx memory append <text...>`, `cdx memory --global append <text...>`, or `cdx memory --project A append <text...>` to append a note without replacing existing content.
- AC7: A user can run `cdx memory list [--json]` to list global memory, named project memories, and the current workspace memory when present, without scanning arbitrary repos or provider memory stores.
- AC8: Append creates the selected memory file when missing, preserves existing content, inserts a clean newline boundary, trims only surrounding whitespace from the appended note, and rejects an empty note.
- AC9: JSON responses for `cdx memory` actions expose the selected scope, project selector when present, path, byte count when applicable, and action names that automation can distinguish from legacy `context.*` actions.
- AC10: `cdx context` remains fully backward compatible; existing scripts, help output, handoff behavior, and current-workspace context file layout keep working.
- AC11: Help and README documentation explain `cdx memory` as the user-facing memory command, document current/global/project scopes, `list`, and mention that it reuses user-controlled Markdown storage rather than provider-private memory databases.
- AC12: Focused tests cover append behavior in the store, the `cdx memory` alias, global and project selectors, list output, JSON output, no-context display, empty append rejection, and preservation of existing `cdx context` behavior.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_006_workspace_memory_command_for_cdx`
- Architecture decision(s): (none yet)

# References
- src/context_store.py
- src/cli_commands.py
- src/cli_args.py
- src/cli.py
- src/cli_render.py
- README.md
- test/test_context_store_py.py
- test/test_cli_py.py

# AI Context
- Summary: Add a small workspace memory command to cdx
- Keywords: request-chain-scaffold, add a small workspace memory command to cdx, development-ready
- Use when: You need to implement or review the scaffolded workflow for Add a small workspace memory command to cdx.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_033_scoped_memory_alias_and_append_command`
