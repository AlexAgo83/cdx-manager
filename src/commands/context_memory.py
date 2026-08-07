"""Context and memory domain commands: context, memory.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import os
import sys

from ..cli_args import CONTEXT_USAGE, MEMORY_USAGE, _parse_json_flag
from ..cli_helpers import _format_bytes, _json_success, _write_json
from ..cli_render import _dim, _pad_table, _success
from ..context_store import (
    append_context,
    append_context_path,
    clear_context,
    clear_context_path,
    edit_context,
    edit_context_path,
    get_context_path,
    get_global_context_path,
    get_named_project_context_path,
    init_context,
    init_context_path,
    list_named_project_contexts,
    read_context,
    read_context_path,
    write_context,
    write_context_path,
)
from ..errors import CdxError


def handle_context(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if not args:
        args = ["show"]
    action = args[0]
    base_dir = ctx["service"]["base_dir"]
    cwd = ctx.get("cwd")

    if action == "show":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        content = read_context(base_dir, cwd)
        payload = {
            "path": get_context_path(base_dir, cwd),
            "exists": bool(content.strip()),
            "content": content,
        }
        if json_flag:
            _write_json(ctx, _json_success("context.show", "Loaded shared context", context=payload))
            return 0
        if content.strip():
            ctx["out"](content if content.endswith("\n") else f"{content}\n")
        else:
            ctx["out"](f"{_dim('No shared context for this workspace. Run: cdx context init or cdx context set <text>', ctx['use_color'])}\n")
        return 0

    if action == "path":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        path = get_context_path(base_dir, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.path", "Resolved shared context path", path=path))
            return 0
        ctx["out"](f"{path}\n")
        return 0

    if action == "init":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = init_context(base_dir, cwd)
        message = "Created shared context" if result.get("created") else "Shared context already exists"
        if json_flag:
            _write_json(ctx, _json_success("context.init", message, context=result))
            return 0
        text = f"{message}: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "edit":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = edit_context(
            base_dir,
            cwd,
            env=ctx.get("env"),
            spawn_sync=ctx.get("spawn_sync"),
        )
        if json_flag:
            _write_json(ctx, _json_success("context.edit", "Edited shared context", context=result))
            return 0
        text = f"Edited shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "clear":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = clear_context(base_dir, cwd)
        message = "Cleared shared context" if result["removed"] else "No shared context to clear"
        if json_flag:
            _write_json(ctx, _json_success("context.clear", message, context=result))
            return 0
        ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        return 0

    if action == "set":
        content_args = args[1:]
        if content_args:
            content = " ".join(content_args)
        else:
            stdin = ctx["options"].get("stdin_data")
            if stdin is None and not ctx.get("stdin_is_tty"):
                stdin = sys.stdin.read()
            if stdin is None:
                raise CdxError("Usage: cdx context set <text> [--json]")
            content = stdin
        result = write_context(base_dir, content, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.set", "Saved shared context", context=result))
            return 0
        text = f"Saved shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "append":
        note = " ".join(args[1:])
        if not note.strip():
            raise CdxError("Usage: cdx context append <text> [--json]")
        result = append_context(base_dir, note, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.append", "Appended shared context", context=result))
            return 0
        text = f"Appended shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    raise CdxError(CONTEXT_USAGE)

def _parse_memory_args(rest):
    json_flag, args = _parse_json_flag(rest)
    scope = "current"
    project = None
    cleaned = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--global":
            if scope != "current":
                raise CdxError(MEMORY_USAGE)
            scope = "global"
            index += 1
            continue
        if arg == "--project":
            if scope != "current" or index + 1 >= len(args) or not args[index + 1].strip():
                raise CdxError(MEMORY_USAGE)
            scope = "project"
            project = args[index + 1].strip()
            index += 2
            continue
        if arg.startswith("--project="):
            if scope != "current":
                raise CdxError(MEMORY_USAGE)
            project = arg.split("=", 1)[1].strip()
            if not project:
                raise CdxError(MEMORY_USAGE)
            scope = "project"
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    if not cleaned:
        cleaned = ["show"]
    if cleaned[0] == "view":
        cleaned[0] = "show"
    return json_flag, scope, project, cleaned

def _memory_target(base_dir, cwd, scope, project):
    if scope == "global":
        return {"scope": "global", "path": get_global_context_path(base_dir)}
    if scope == "project":
        if os.path.exists(project):
            return {
                "scope": "project",
                "project": project,
                "project_kind": "path",
                "path": get_context_path(base_dir, project),
            }
        return {
            "scope": "project",
            "project": project,
            "project_kind": "name",
            "path": get_named_project_context_path(base_dir, project),
        }
    return {"scope": "current", "path": get_context_path(base_dir, cwd)}

def _memory_payload(target, content=None):
    payload = {
        "scope": target["scope"],
        "path": target["path"],
        "exists": os.path.isfile(target["path"]),
    }
    if target.get("project") is not None:
        payload["project"] = target["project"]
        payload["project_kind"] = target.get("project_kind")
    if payload["exists"]:
        payload["bytes"] = os.path.getsize(target["path"])
    if content is not None:
        payload["content"] = content
    return payload

def _list_memory_entries(base_dir, cwd):
    entries = []
    global_path = get_global_context_path(base_dir)
    if os.path.isfile(global_path):
        entries.append({"scope": "global", "path": global_path, "bytes": os.path.getsize(global_path)})
    entries.extend(list_named_project_contexts(base_dir))
    current_path = get_context_path(base_dir, cwd)
    if os.path.isfile(current_path):
        entries.append({"scope": "current", "path": current_path, "bytes": os.path.getsize(current_path)})
    return entries

def handle_memory(rest, ctx):
    json_flag, scope, project, args = _parse_memory_args(rest)
    action = args[0]
    base_dir = ctx["service"]["base_dir"]
    cwd = ctx.get("cwd")

    if action == "list":
        if len(args) != 1 or scope != "current":
            raise CdxError(MEMORY_USAGE)
        entries = _list_memory_entries(base_dir, cwd)
        if json_flag:
            _write_json(ctx, _json_success("memory.list", "Listed memory scopes", memories=entries))
            return 0
        if not entries:
            ctx["out"](f"{_dim('No cdx memory files found.', ctx['use_color'])}\n")
            return 0
        rows = [["SCOPE", "PROJECT", "SIZE", "PATH"]]
        for entry in entries:
            rows.append([
                entry["scope"],
                entry.get("project") or "-",
                _format_bytes(entry.get("bytes") or 0),
                entry["path"],
            ])
        ctx["out"](_pad_table(rows) + "\n")
        return 0

    target = _memory_target(base_dir, cwd, scope, project)
    path = target["path"]

    if action == "show":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        content = read_context_path(path)
        payload = _memory_payload(target, content=content)
        if json_flag:
            _write_json(ctx, _json_success("memory.show", "Loaded memory", memory=payload))
            return 0
        if content.strip():
            ctx["out"](content if content.endswith("\n") else f"{content}\n")
        else:
            ctx["out"](f"{_dim('No memory for this scope. Run: cdx memory append <text>', ctx['use_color'])}\n")
        return 0

    if action == "path":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        if json_flag:
            _write_json(ctx, _json_success("memory.path", "Resolved memory path", memory=_memory_payload(target)))
            return 0
        ctx["out"](f"{path}\n")
        return 0

    if action == "init":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        result = init_context_path(path)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        message = "Created memory" if result.get("created") else "Memory already exists"
        if json_flag:
            _write_json(ctx, _json_success("memory.init", message, memory=result))
            return 0
        ctx["out"](f"{_success(f'{message}: {path}', ctx['use_color'])}\n")
        return 0

    if action == "edit":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        result = edit_context_path(path, env=ctx.get("env"), spawn_sync=ctx.get("spawn_sync"))
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        if json_flag:
            _write_json(ctx, _json_success("memory.edit", "Edited memory", memory=result))
            return 0
        ctx["out"](f"{_success(f'Edited memory: {path}', ctx['use_color'])}\n")
        return 0

    if action == "clear":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        result = clear_context_path(path)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        message = "Cleared memory" if result["removed"] else "No memory to clear"
        if json_flag:
            _write_json(ctx, _json_success("memory.clear", message, memory=result))
            return 0
        ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        return 0

    if action == "set":
        content_args = args[1:]
        if content_args:
            content = " ".join(content_args)
        else:
            stdin = ctx["options"].get("stdin_data")
            if stdin is None and not ctx.get("stdin_is_tty"):
                stdin = sys.stdin.read()
            if stdin is None:
                raise CdxError("Usage: cdx memory set <text> [--json]")
            content = stdin
        result = write_context_path(path, content)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        if json_flag:
            _write_json(ctx, _json_success("memory.set", "Saved memory", memory=result))
            return 0
        ctx["out"](f"{_success(f'Saved memory: {path}', ctx['use_color'])}\n")
        return 0

    if action == "append":
        note = " ".join(args[1:])
        result = append_context_path(path, note)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        if json_flag:
            _write_json(ctx, _json_success("memory.append", "Appended memory", memory=result))
            return 0
        ctx["out"](f"{_success(f'Appended memory: {path}', ctx['use_color'])}\n")
        return 0

    raise CdxError(MEMORY_USAGE)
