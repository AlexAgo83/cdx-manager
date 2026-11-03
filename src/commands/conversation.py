"""JSON conversation pages for interactive sessions."""

from ..cli_args import _parse_flag_args
from ..cli_helpers import _json_success, _write_json
from ..conversation import read_conversation
from ..errors import CdxError
from ..provider_runtime import _get_auth_home

CONVERSATION_USAGE = "Usage: cdx conversation <name> [--conversation ID] [--cursor CURSOR] [--limit N] --json"


def handle_conversation(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--conversation": {"key": "conversation", "type": "str"},
        "--cursor": {"key": "cursor", "type": "str"},
        "--limit": {"key": "limit", "type": "str", "default": "100"},
    }, CONVERSATION_USAGE, positionals_key="names", max_positionals=1)
    if not parsed["json"] or len(parsed["names"]) != 1:
        raise CdxError(CONVERSATION_USAGE)
    session = ctx["service"]["get_session"](parsed["names"][0])
    if not session:
        raise CdxError(f"Unknown session: {parsed['names'][0]}")
    try:
        limit = int(parsed["limit"])
    except ValueError:
        raise CdxError(CONVERSATION_USAGE) from None
    page = read_conversation(
        session["provider"], _get_auth_home(session),
        conversation_id=parsed["conversation"] or (session.get("conversation") or {}).get("id"),
        cursor=parsed["cursor"], limit=limit,
    )
    _write_json(ctx, _json_success("conversation", "Conversation page loaded.", session=session["name"], **page))
    return 0
