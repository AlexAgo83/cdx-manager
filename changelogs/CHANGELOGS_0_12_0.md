# CDX Manager 0.12.0

## Highlights

- Added explicit `cdx memory` management for current workspace, global, and project-scoped memory.
- Added append/list workflows for user-controlled Markdown memory without touching provider-private memory stores.
- Improved `cdx doctor` provider visibility with Codex and Claude CLI versions plus conservative capability hints.

## Changes

### Scoped memory

`cdx memory` now manages explicit local memory using the existing shared context store:

- `cdx memory append <text>` appends to the current workspace memory.
- `cdx memory --global append <text>` appends to a global operator memory.
- `cdx memory --project <name> append <text>` appends to a stable named project memory.
- `cdx memory --project <path> ...` resolves to the same workspace-hash memory used by that repo path.
- `cdx memory list [--json]` lists global memory, named project memories, and the current workspace memory when present.

Append is intentionally plain text with a clean newline boundary; it does not add dates or headings automatically.

### Context compatibility

`cdx context append <text>` was added for the existing workspace context command. Existing `cdx context` and `cdx handoff` behavior remains compatible.

### Doctor provider versions

`cdx doctor` now records provider CLI versions when available:

- `codex --version`
- `claude --version`

JSON output includes conservative capability hints for recent provider memory and diagnostic surfaces. These hints are informational; `cdx` still does not read or write Codex SQLite memory, Claude Code project memory, `CLAUDE.md`, or provider plugin files.

## Validation

- `PYTHONPATH=src python3 -m pytest -q`
- `python3 -m ruff check src test`
- `logics-manager flow validate req_013_add_a_small_workspace_memory_command_to_cdx`
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
