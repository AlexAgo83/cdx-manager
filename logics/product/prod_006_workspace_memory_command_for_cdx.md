## prod_006_workspace_memory_command_for_cdx - Workspace memory command for cdx
> Date: 2026-07-28
> Status: Settled
> Related request: `req_013_add_a_small_workspace_memory_command_to_cdx`
> Related backlog: `item_033_scoped_memory_alias_and_append_command`
> Related task: `task_024_orchestrate_workspace_memory_command`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.
> Non-semantic edit: provider-signal/list framing added; workflow state and linked refs unchanged.

# Overview
Expose the existing shared context storage as a clearer `cdx memory` command, with current-workspace, global, and explicit project scopes plus minimal append and list operations for durable notes. The command reuses user-controlled Markdown context files and handoff flow so assistant sessions can share memory without depending on provider-private databases.

```mermaid
%% logics-kind: product
flowchart TD
    User[User] --> Memory[cdx memory]
    Memory --> Current[Current repo memory]
    Memory --> Global[Global memory]
    Memory --> Project[Selected project memory]
    Current --> Store[Markdown context store]
    Global --> Store
    Project --> Store
    Store --> Handoff[Existing cdx handoff]
```

# Goals
- Make the existing workspace context easier to discover as project memory.
- Let users maintain current-workspace, global, and explicitly selected project memory.
- Let users append short notes or decisions without opening an editor or rewriting the full context.
- Let users list known memory scopes without scanning arbitrary repositories.
- Keep one storage model based on user-controlled Markdown files under `~/.cdx/contexts/`.
- Keep `cdx context` and `cdx handoff` behavior compatible for existing users and scripts.
- Avoid provider-private memory internals and expose only user-controlled Markdown memory.

# Non-goals
- Reading or writing provider-owned SQLite memory files.
- Adding a new memory database, sync service, daemon, or background summarizer.
- Automatic extraction of memories from transcripts.
- Memory search, tagging, ranking, pruning, or semantic recall.
- Complex project registry management beyond resolving a simple project name or path to a stable local memory file and listing named project memories created by `cdx`.
- Changing how provider sessions launch beyond existing handoff context installation.

# Scope and guardrails
- In: current-workspace memory, global memory, explicit project memory selection, append/set/view/path/init/edit/clear/list commands, JSON output, docs, and focused tests.
- Out: provider-owned memory databases, automatic summarization, memory search, repository discovery, cross-machine sync, remote APIs, and changes to provider launch behavior beyond existing handoff context installation.

# Recent provider signals
- Codex now has stronger memory/import surfaces, including import paths from other agents. `cdx memory` should be a stable local Markdown target that future import/export features can use.
- Claude Code now documents project auto memory under its own `~/.claude/projects/<project>/memory/` tree and exposes `/memory` for editing. `cdx` should not write there in v1; a later sync/export command can be designed once users prove they need it.
- Claude Code model aliases, Opus/Sonnet generation changes, effort limits, fast mode, and stream-json diagnostics are adjacent `cdx doctor` / `cdx run --json` opportunities, not requirements for this memory slice.

# Key product decisions
- `cdx memory` is a user-facing alias over user-controlled Markdown memory; it must reuse the existing context store instead of introducing a second persistence model.
- The default scope is the current workspace/repo. `--global` selects one operator-wide memory, and `--project <name-or-path>` selects a specific project memory from any cwd.
- `--project A` is a stable free-form project name, while `--project /path/to/repo` resolves through the existing workspace hash behavior for that path.
- `append` is intentionally line-oriented and simple: add the provided note, preserve existing content, and reject empty input. It should not auto-date or reformat notes.
- `list` is intentionally bounded: show global memory, named project memories, and the current workspace memory when present. Do not scan the filesystem to discover repositories.
- `cdx context` remains the compatibility surface for existing scripts; `cdx memory` is the clearer operator-facing surface.
- Provider-private files such as `profiles/*/memories_*.sqlite` are not part of the supported memory contract.

# Follow-up candidates
- `cdx doctor` could warn when Claude Code or Codex CLI versions are too old for configured models, fast mode, or headless JSON features.
- `cdx run --json` could capture richer Claude Code stream-json init diagnostics such as MCP config validation errors when those fields are present.
- `cdx memory export|sync` could later write explicit user-approved context into provider-native memory files or instruction files, but only after the scoped Markdown memory command ships.

# Success signals
- Users can inspect and update memory without knowing the hashed context path.
- A global note and a project-specific note can be appended from any repo without modifying the wrong memory file.
- Users can list global and named project memories without needing to remember exact storage paths.
- Existing `cdx context` and `cdx handoff` workflows continue to pass their current tests.
- JSON output identifies the action and selected scope clearly enough for automation.
- The implementation stays small: one storage model, one append helper, and no provider-private memory handling.

# References
- Product back-reference: `req_013_add_a_small_workspace_memory_command_to_cdx`
- Task back-reference: `task_024_orchestrate_workspace_memory_command`
