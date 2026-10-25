"""cdx rescue: move a conversation stopped by a usage limit to an account that can go on.

Everything it does already exists -- `status` knows which accounts are spent,
the shared ranking knows which one is best, `handoff` carries a conversation
over. This command only puts them in one step, and asks before it does.
"""

import os
from datetime import datetime, timedelta, timezone

from ..cli_helpers import _json_failure, _json_success, _write_json
from ..cli_render import _info, _warn
from ..errors import CdxError
from ..session_ranking import rank_sessions
from ..status_view import _now_timestamp, _priority_reset_timestamp
from .launch import handle_handoff

RESCUE_USAGE = "Usage: cdx rescue [<session>] [--to <target>] [--yes] [--dry-run] [--json]"
#: A conversation stopped longer ago than this is history, not something to rescue.
RECENT = timedelta(hours=24)


def _parse(rest):
    parsed = {"source": None, "target": None, "yes": False, "dry_run": False, "json": False}
    index = 0
    while index < len(rest):
        arg = rest[index]
        if arg == "--to" and index + 1 < len(rest):
            parsed["target"] = rest[index + 1]
            index += 1
        elif arg in ("--yes", "-y"):
            parsed["yes"] = True
        elif arg == "--dry-run":
            parsed["dry_run"] = True
        elif arg == "--json":
            parsed["json"] = True
        elif not arg.startswith("-") and parsed["source"] is None:
            parsed["source"] = arg
        else:
            raise CdxError(RESCUE_USAGE)
        index += 1
    return parsed


def _recent(iso, now):
    try:
        when = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return now - when <= RECENT


def stranded(service, rows, now=None):
    """Sessions on a spent account whose last conversation can be handed off, newest first."""
    now = now or datetime.now(timezone.utc)
    found = []
    for session in service["list_sessions"]():
        row = rows.get(session["name"]) or {}
        conversation = (session.get("conversation") or {}).get("id")
        if row.get("available_pct") != 0 or not conversation or not _recent(row.get("last_launched_at"), now):
            continue
        history = service["get_launch_history"](session["name"], limit=1)
        cwd = (history[0].get("cwd") if history else None) or None
        if not cwd or not os.path.isdir(cwd):
            continue
        found.append({
            "session": session["name"], "provider": session["provider"], "conversation_id": conversation,
            "cwd": cwd, "reset_at": row.get("reset_at"), "last_launched_at": row.get("last_launched_at"),
        })
    return sorted(found, key=lambda item: item["last_launched_at"] or "", reverse=True)


def pick_target(rows, source, provider):
    """(target row, needs confirmation) for the best ready account, or (None, False).

    `use` accounts first; an `ask-first` one only when no `use` account is
    ready, and always behind a confirmation. `never` is not considered.
    """
    others = [row for row in rows.values() if row.get("session_name") != source]
    ordered, _ = rank_sessions(others, _now_timestamp(), _priority_reset_timestamp,
                               provider=provider, require_ready=True)
    if ordered:
        return ordered[0], False
    asked = [{**row, "policy": "use"} for row in others if row.get("policy") == "ask-first"]
    ordered, _ = rank_sessions(asked, _now_timestamp(), _priority_reset_timestamp,
                               provider=provider, require_ready=True)
    return (ordered[0], True) if ordered else (None, False)


def handle_rescue(rest, ctx):
    parsed = _parse(rest)
    service = ctx["service"]
    rows = {row["session_name"]: row for row in service["get_status_rows"](force_refresh=False)}
    candidates = stranded(service, rows)
    if parsed["source"]:
        candidates = [c for c in candidates if c["session"] == parsed["source"]]
    if not candidates:
        message = "No conversation stopped by a usage limit in the last 24 hours."
        if parsed["json"]:
            _write_json(ctx, _json_success("rescue", message, plan=None, stranded=[]))
        else:
            ctx["out"](f"{message}\n")
        return 0
    source = candidates[0]
    if parsed["target"]:
        target = rows.get(parsed["target"])
        if not target or target.get("policy") == "never":
            raise CdxError(f"Cannot rescue onto {parsed['target']}: unknown account or policy never.")
        confirm = target.get("policy") == "ask-first"
    else:
        target, confirm = pick_target(rows, source["session"], source["provider"])
    if not target:
        message = f"No ready {source['provider']} account to take over {source['session']}."
        if parsed["json"]:
            _write_json(ctx, _json_failure("rescue", "no_ready_account", message, stranded=candidates))
            return 1
        raise CdxError(message)
    plan = {**source, "target": target["session_name"], "target_policy": target.get("policy", "use")}
    if parsed["json"] or parsed["dry_run"]:
        if parsed["json"]:
            _write_json(ctx, _json_success("rescue", "Rescue plan", plan=plan, stranded=candidates))
        else:
            ctx["out"](_describe(plan, ctx) + "\n")
        return 0
    ctx["out"](_describe(plan, ctx) + "\n")
    if confirm or not parsed["yes"]:
        if not ctx["stdin_is_tty"]:
            raise CdxError("cdx rescue needs a terminal to confirm; pass --yes (not enough for an ask-first account).")
        ask = ctx.get("options", {}).get("input") or input
        question = f"Hand {source['session']} over to {target['session_name']}"
        question += " (policy ask-first)" if confirm else ""
        if ask(f"{question}? [y/N] ").strip().lower() not in ("y", "yes"):
            raise CdxError("Rescue cancelled.", exit_code=130)
    return handle_handoff(
        [source["session"], target["session_name"], "--source-conversation", source["conversation_id"]],
        {**ctx, "cwd": source["cwd"]},
    )


def _describe(plan, ctx):
    reset = f", back {plan['reset_at']}" if plan.get("reset_at") else ""
    lines = [
        _warn(f"{plan['session']} is out of usage{reset}", ctx["use_color"]),
        f"  conversation {plan['conversation_id']} in {plan['cwd']}",
        _info(f"-> {plan['target']}" + (" (ask-first)" if plan["target_policy"] == "ask-first" else ""), ctx["use_color"]),
    ]
    return "\n".join(lines)
