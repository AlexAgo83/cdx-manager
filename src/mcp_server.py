"""`cdx mcp serve`: the cdx CLI as a stdio MCP server.

Each tool runs one non-interactive `cdx ... --json` command of this same install and
returns its JSON. Only reading and running are wired: status, configs, run (blocking or
detached), runs, run-status, run-report, run-tail, history, stats, disk, ready, last and
doctor. Subcommands that delete, touch credentials or change settings (rmv, clean, reset,
export, import, login, logout, set, update, ...) have no tool on purpose: adding one is a
code change, which is the confirmation gate. `reset` is not a context clear: it spends a
banked Codex rate-limit reset credit.

`cdx run` needs a working directory. A client names a project by its short name, which
resolves to `<project root>/<name>`; the root comes from `--project-root` or
CDX_MCP_PROJECT_ROOT and is never guessed. To serve another machine, make the MCP client's
command an SSH call that runs `cdx mcp serve` there: stdio passes through unchanged.

No dependency: the MCP SDK is not installed where cdx runs.
"""

import json
import os
import re
import subprocess
import sys

from .commands.runs import _cdx_self_command
from .errors import CdxError

PROJECT_ROOT_ENV = "CDX_MCP_PROJECT_ROOT"
MCP_USAGE = "Usage: cdx mcp serve [--project-root DIR]"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
MODEL_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SINCE_RE = re.compile(r"^[A-Za-z0-9:-]+$")
TIMEOUT = 600
LEVELS = ["minimal", "low", "medium", "high", "xhigh"]
PERMISSIONS = ["review", "default", "auto", "full", "workspace-write", "read-only", "danger-full-access"]


class ToolError(Exception):
    """A tool-facing failure; its message goes back to the client as the tool result."""


def _string(description, enum=None):
    return {"type": "string", "description": description, **({"enum": enum} if enum else {})}


_RUN_PROPERTIES = {
    "project": _string("Short project name, resolved under the server's project root. Never a path."),
    "prompt": _string("Prompt text. Sent on standard input, never on a command line."),
    "session": _string("Session name. Mutually exclusive with `provider`: omit it to let cdx pick a ready session of that provider."),
    "provider": _string("Let cdx pick a ready session of this provider, when no `session` is named."),
    "model": _string("Model override."),
    "kind": _string("Run kind.", ["assistant", "code-review"]),
    "reasoning_effort": _string("Reasoning effort.", LEVELS),
    "power": _string("Power level.", LEVELS),
    "permission": _string("Permission (default `full`: lower levels cut network access in Codex sandboxes).", PERMISSIONS),
    "timeout_seconds": {"type": "integer", "description": "Run timeout, 1 to 3600 seconds."},
}

TOOLS = [
    ("cdx_status", "Get session status. Omit `session` for the overview of all sessions.",
     {"session": _string("Session name."), "refresh": {"type": "boolean"}}, []),
    ("cdx_configs", "List configured sessions, or show one session's configuration by `name`.",
     {"name": _string("Session name. Omit to list all; never pass `configs`.")}, []),
    ("cdx_run", "Run a prompt in a project and block until it finishes. Use cdx_run_background for anything longer than a few minutes.",
     _RUN_PROPERTIES, ["project", "prompt"]),
    ("cdx_run_background", "Launch a detached run and return its run_id at once; follow it with cdx_run_status or cdx_run_tail.",
     _RUN_PROPERTIES, ["project", "prompt"]),
    ("cdx_runs", "List recent runs, including the ones still running.", {"limit": {"type": "integer"}}, []),
    ("cdx_run_status", "Check one run by run_id.", {"run_id": _string("Run id.")}, ["run_id"]),
    ("cdx_run_report", "Get the report of a finished run.", {"run_id": _string("Run id.")}, ["run_id"]),
    ("cdx_run_tail", "Show the last lines of a run's output while it runs.",
     {"run_id": _string("Run id."), "lines": {"type": "integer", "description": "1 to 2000, default 50."}}, ["run_id"]),
    ("cdx_history", "Show run history, optionally by session and time window.",
     {"session": _string("Session name."), "limit": {"type": "integer"}, "summary": {"type": "boolean"},
      "since": _string("7d, today or a date.")}, []),
    ("cdx_stats", "Show aggregated usage, optionally by session and time window.",
     {"session": _string("Session name."), "since": _string("7d, today or a date."),
      "date_from": _string("Start date."), "date_to": _string("End date.")}, []),
    ("cdx_disk", "Show disk usage; `profiles` scopes to profile storage, `candidates` lists cleanup candidates.",
     {"profiles": {"type": "boolean"}, "candidates": {"type": "boolean"}}, []),
    ("cdx_ready", "Check which sessions can take a run.", {"refresh": {"type": "boolean"}}, []),
    ("cdx_last", "Get the most recent run across all sessions.", {}, []),
    ("cdx_doctor", "Run the cdx health check.", {}, []),
]


def tool_definitions():
    return [{"name": name, "description": description,
             "inputSchema": {"type": "object", "properties": properties, "required": required,
                             "additionalProperties": False}}
            for name, description, properties, required in TOOLS]


def _name(value, field):
    # Dots alone would climb out of the project root.
    if not isinstance(value, str) or not NAME_RE.fullmatch(value) or set(value) == {"."}:
        raise ToolError(f"invalid {field}: {value!r} (allowed: letters, digits, '.', '_', '-')")
    return value


def _choice(value, allowed, field):
    if value is not None and value not in allowed:
        raise ToolError(f"invalid {field}: {value!r} (allowed: {allowed})")


def _pattern(value, pattern, field):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ToolError(f"invalid {field}: {value!r}")
    return value


def _int(value, field, low, high):
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ToolError(f"{field} must be an integer between {low} and {high}, got {value!r}")
    return str(value)


def run_cdx(args, input_text=None, timeout=TIMEOUT):
    """Run this install's cdx with `args`; stdin is never the MCP stream."""
    command, package_root = _cdx_self_command()
    env = dict(os.environ)
    if package_root:
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH")]))
    try:
        proc = subprocess.run(command + args, input=input_text or "", capture_output=True,
                              text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as error:
        raise ToolError(f"timeout after {timeout}s waiting on cdx; a run may still be going, check cdx_runs") from error
    text = proc.stdout.strip()
    try:
        data = json.loads(text)
    except ValueError as error:
        raise ToolError(f"cdx {args[0]}: no JSON (exit {proc.returncode}). stdout: {text[:500]!r} "
                        f"stderr: {proc.stderr.strip()[:500]!r}") from error
    if proc.returncode != 0 and isinstance(data, dict) and data.get("ok") is False:
        error = data.get("error") or {}
        raise ToolError(f"cdx {args[0]} failed: {error.get('message', 'unknown error')} "
                        f"(code={error.get('code')}, exit={proc.returncode})")
    return data


def _run_args(arguments, project_root, detach):
    if not project_root:
        raise ToolError(f"no project root: start the server with --project-root or {PROJECT_ROOT_ENV}")
    cwd = os.path.join(project_root, _name(arguments.get("project"), "project"))
    prompt = arguments.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ToolError("prompt is required")
    session = arguments.get("session")
    provider = arguments.get("provider")
    # cdx run rejects both with an opaque usage error that once passed for a launch.
    if session and provider:
        raise ToolError(f"pass session={session!r} or provider={provider!r}, not both: each session already "
                        "has its provider; omit session to auto-select by provider")
    if not session and not provider:
        raise ToolError("pass a session or a provider")
    parts = ["run"] + ([_name(session, "session")] if session else [])
    parts += ["--cwd", cwd, "--prompt-file", "-"]
    if provider:
        parts += ["--provider", _name(provider, "provider")]
    if arguments.get("model") is not None:
        parts += ["--model", _pattern(arguments["model"], MODEL_RE, "model")]
    for key, flag, allowed in (("kind", "--kind", ["assistant", "code-review"]),
                               ("reasoning_effort", "--reasoning-effort", LEVELS), ("power", "--power", LEVELS)):
        _choice(arguments.get(key), allowed, key)
        if arguments.get(key):
            parts += [flag, arguments[key]]
    permission = arguments.get("permission") or "full"
    _choice(permission, PERMISSIONS, "permission")
    parts += ["--permission", permission]
    timeout = TIMEOUT
    if arguments.get("timeout_seconds") is not None:
        parts += ["--timeout-seconds", _int(arguments["timeout_seconds"], "timeout_seconds", 1, 3600)]
        timeout = max(TIMEOUT, arguments["timeout_seconds"] + 30)
    parts += ["--detach", "--json"] if detach else ["--json"]
    return parts, prompt, (TIMEOUT if detach else timeout)


def _optional_name(arguments, key, field="session"):
    return [_name(arguments[key], field)] if arguments.get(key) else []


def _window(arguments, keys):
    parts = []
    for key, flag in keys:
        if arguments.get(key):
            parts += [flag, _pattern(arguments[key], SINCE_RE, key)]
    return parts


def build(name, arguments, project_root):
    """(cdx argv, stdin text, timeout) for one tool call."""
    a = arguments
    if name in ("cdx_run", "cdx_run_background"):
        return _run_args(a, project_root, name == "cdx_run_background")
    if name == "cdx_status":
        parts = ["status", *_optional_name(a, "session"), "--json"] + (["--refresh"] if a.get("refresh") else [])
    elif name == "cdx_configs":
        parts = ["config", _name(a["name"], "name"), "--json"] if a.get("name") else ["configs", "--json"]
    elif name == "cdx_runs":
        parts = ["runs", *(["--limit", _int(a["limit"], "limit", 1, 1000)] if a.get("limit") else []), "--json"]
    elif name in ("cdx_run_status", "cdx_run_report"):
        parts = [name[4:].replace("_", "-"), _name(a.get("run_id"), "run_id"), "--json"]
    elif name == "cdx_run_tail":
        parts = ["run-tail", _name(a.get("run_id"), "run_id"), "--lines", _int(a.get("lines", 50), "lines", 1, 2000), "--json"]
    elif name == "cdx_history":
        parts = ["history", *_optional_name(a, "session")]
        parts += ["--limit", _int(a["limit"], "limit", 1, 1000)] if a.get("limit") else []
        parts += ["--summary"] if a.get("summary") else []
        parts += _window(a, [("since", "--since")]) + ["--json"]
    elif name == "cdx_stats":
        parts = ["stats", *_optional_name(a, "session")]
        parts += _window(a, [("since", "--since"), ("date_from", "--from"), ("date_to", "--to")]) + ["--json"]
    elif name == "cdx_disk":
        parts = ["disk"] + (["profiles"] + (["--candidates"] if a.get("candidates") else []) if a.get("profiles") else []) + ["--json"]
    elif name == "cdx_ready":
        parts = ["ready"] + (["--refresh"] if a.get("refresh") else []) + ["--json"]
    elif name in ("cdx_last", "cdx_doctor"):
        parts = [name[4:], "--json"]
    else:
        raise ToolError(f"unknown tool: {name}")
    return parts, None, TIMEOUT


_KNOWN = {name: set(properties) for name, _, properties, _ in TOOLS}


def call_tool(name, arguments, project_root, runner=run_cdx):
    if name not in _KNOWN:
        raise ToolError(f"unknown tool: {name}")
    arguments = arguments or {}
    unknown = sorted(set(arguments) - _KNOWN[name])
    if unknown:
        raise ToolError(f"unsupported argument(s): {', '.join(unknown)}")
    args, input_text, timeout = build(name, arguments, project_root)
    return runner(args, input_text=input_text, timeout=timeout)


def answer(request, project_root, runner=run_cdx):
    """The JSON-RPC reply to one request, or None for a notification."""
    if "id" not in request:
        return None
    method, rid = request.get("method"), request["id"]
    if method == "initialize":
        version = (request.get("params") or {}).get("protocolVersion") or "2025-06-18"
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "cdx", "version": "1"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tool_definitions()}
    elif method == "tools/call":
        params = request.get("params") or {}
        try:
            payload = call_tool(params.get("name"), params.get("arguments"), project_root, runner)
            result = {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
                      "structuredContent": payload if isinstance(payload, dict) else {"result": payload},
                      "isError": False}
        except (ToolError, CdxError) as error:
            result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def serve(project_root, stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        try:
            request = json.loads(line)
        except ValueError:
            continue
        reply = answer(request, project_root) if isinstance(request, dict) else None
        if reply:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()
    return 0


def handle_mcp(rest, ctx):
    if not rest or rest[0] in ("help", "--help", "-h"):
        ctx["out"](f"{MCP_USAGE}\n")
        return 0
    if rest[0] != "serve":
        raise CdxError(MCP_USAGE)
    args = rest[1:]
    project_root = os.environ.get(PROJECT_ROOT_ENV) or None
    if args[:1] == ["--project-root"] and len(args) == 2:
        project_root = args[1]
    elif args:
        raise CdxError(MCP_USAGE)
    if project_root:
        project_root = os.path.abspath(os.path.expanduser(project_root))
        if not os.path.isdir(project_root):
            raise CdxError(f"cdx mcp serve: project root is not a directory: {project_root}")
    return serve(project_root)
