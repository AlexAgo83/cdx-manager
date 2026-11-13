"""JSON conversation pages for interactive sessions."""

import os
import re

from ..cli_args import _parse_flag_args
from ..cli_helpers import _json_success, _write_json
from ..conversation import read_conversation
from ..errors import CdxError
from ..provider_runtime import _get_auth_home

CONVERSATION_USAGE = "Usage: cdx conversation <name> [--conversation ID | --pid PID | --process-identity ID] [--cwd PATH] [--since ISO] [--cursor CURSOR | --tail N | --before CURSOR] [--limit N] --json"


def _remote_endpoint(ctx, session, pid):
    """The endpoint file of the launch whose TUI is `pid` (read only, never created here).

    Concurrent launches of one session each own a file; the pointer file only
    names the most recent, so it is the fallback.
    """
    base_dir = ctx["service"].get("base_dir")
    if not base_dir:
        return None
    from ..remote_control import live_endpoints

    for path, info in live_endpoints(base_dir, session["name"]):
        if pid is not None and info.get("tui_pid") == pid:
            return path
    return os.path.join(base_dir, "state", "remote", f"{session['name']}.endpoint.json")


def _identity_pid(identity):
    match = re.fullmatch(r"linux:(\d+):[0-9a-f]{64}", identity or "")
    return int(match[1]) if match else None


def handle_conversation(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--conversation": {"key": "conversation", "type": "str"},
        "--pid": {"key": "pid", "type": "str"},
        "--process-identity": {"key": "process_identity", "type": "str"},
        "--cwd": {"key": "cwd", "type": "str"},
        "--since": {"key": "since", "type": "str"},
        "--tail": {"key": "tail", "type": "str"},
        "--before": {"key": "before", "type": "str"},
        "--cursor": {"key": "cursor", "type": "str"},
        "--limit": {"key": "limit", "type": "str", "default": "100"},
    }, CONVERSATION_USAGE, positionals_key="names", max_positionals=1)
    if not parsed["json"] or len(parsed["names"]) != 1:
        raise CdxError(CONVERSATION_USAGE)
    session = ctx["service"]["get_session"](parsed["names"][0])
    if not session:
        raise CdxError(f"Unknown session: {parsed['names'][0]}")
    try:
        pid = int(parsed["pid"]) if parsed["pid"] is not None else None
        limit = int(parsed["limit"])
        tail = int(parsed["tail"]) if parsed["tail"] is not None else None
    except ValueError:
        raise CdxError(CONVERSATION_USAGE) from None
    process_selected = parsed["pid"] is not None or parsed["process_identity"] is not None
    if parsed["pid"] is not None and parsed["process_identity"] is not None:
        raise CdxError(CONVERSATION_USAGE)
    page = read_conversation(
        session["provider"], _get_auth_home(session),
        conversation_id=parsed["conversation"] or (None if process_selected else (session.get("conversation") or {}).get("id")),
        pid=pid, process_identity=parsed["process_identity"],
        remote_endpoint=_remote_endpoint(ctx, session, pid if pid is not None else _identity_pid(parsed["process_identity"])) if process_selected else None,
        cwd=parsed["cwd"], started_at=parsed["since"],
        cursor=parsed["cursor"], limit=limit, tail=tail, before=parsed["before"], fallback_to_recency=not process_selected and not parsed["conversation"],
    )
    _write_json(ctx, _json_success("conversation", "Conversation page loaded.", session=session["name"], **page))
    return 0
