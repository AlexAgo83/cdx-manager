"""Session lifecycle domain commands: add, cp, ren, rmv, label, enable, disable.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

from ..cli_args import (
    _parse_add_args,
    _parse_copy_args,
    _parse_json_flag,
    _parse_label_args,
    _parse_remove_args,
    _parse_rename_args,
    _parse_toggle_args,
)
from ..cli_helpers import _bootstrap_claude_setup_token, _json_success, _local_now_iso, _resolve_confirmation, _write_json
from ..cli_render import _success, _warn
from ..config import PROVIDER_CLAUDE, PROVIDER_OLLAMA
from ..errors import CdxError
from ..provider_runtime import _ensure_session_authentication


def _confirm_removal(name):
    answer = input(f"Remove session {name}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")

def handle_add(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_add_args(args)
    if parsed["provider"] == PROVIDER_OLLAMA and not parsed.get("model"):
        raise CdxError("Usage: cdx add ollama <name> --model MODEL [--json]")
    if parsed.get("model") and parsed["provider"] != PROVIDER_OLLAMA:
        raise CdxError("--model is only supported when adding an ollama session.")
    session = ctx["service"]["create_session"](parsed["name"], parsed["provider"])
    if parsed.get("model"):
        session = ctx["service"]["set_launch_settings"](parsed["name"], {"model": parsed["model"]})
    message = f"Created session {parsed['name']} ({parsed['provider']})"
    if session["provider"] == PROVIDER_CLAUDE and ctx["stdin_is_tty"]:
        # ponytail: mint a ~1yr setup-token instead of the ~daily claude login token
        _bootstrap_claude_setup_token(session, ctx)
    else:
        _ensure_session_authentication(
            session,
            ctx["service"],
            spawn=ctx.get("spawn"),
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
            stdin_is_tty=ctx["stdin_is_tty"],
            behavior="bootstrap",
            signal_emitter=ctx.get("signal_emitter"),
        )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](parsed["name"], lambda auth: {
        **auth,
        "status": "authenticated",
        "lastCheckedAt": now,
        "lastAuthenticatedAt": now,
        "lastLoggedOutAt": auth.get("lastLoggedOutAt"),
    })
    if json_flag:
        _write_json(ctx, _json_success(
            "add",
            message,
            session=ctx["service"]["get_session"](parsed["name"]),
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_copy(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_copy_args(args)
    result = ctx["service"]["copy_session"](parsed["source"], parsed["dest"])
    overwritten = " (overwritten)" if result["overwritten"] else ""
    message = f"Copied session {parsed['source']} to {parsed['dest']}{overwritten}"
    if json_flag:
        _write_json(ctx, _json_success(
            "copy",
            message,
            session=result["session"],
            overwritten=result["overwritten"],
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_rename(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_rename_args(args)
    session = ctx["service"]["rename_session"](parsed["source"], parsed["dest"])
    message = f"Renamed session {parsed['source']} to {parsed['dest']}"
    if json_flag:
        _write_json(ctx, _json_success("rename", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_label(rest, ctx):
    parsed = _parse_label_args(rest)
    if parsed["clear"]:
        session = ctx["service"]["clear_session_label"](parsed["name"])
        message = f"Cleared label for {parsed['name']}"
    else:
        session = ctx["service"]["set_session_label"](parsed["name"], parsed["label"])
        message = f"Set label for {parsed['name']}: {session['label']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("label", message, session=session, label=session.get("label")))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_remove(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_remove_args(args)
    if not parsed["force"]:
        confirm_fn = ctx["options"].get("confirmRemove")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, parsed["name"])
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Removal requires confirmation in an interactive terminal or --force in non-interactive mode.")
        else:
            confirmed = _confirm_removal(parsed["name"])
        if not confirmed:
            if json_flag:
                _write_json(ctx, _json_success("remove", "Cancelled.", cancelled=True, session=None))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0
    removed = ctx["service"]["remove_session"](parsed["name"])
    message = f"Removed session {parsed['name']}"
    if json_flag:
        _write_json(ctx, _json_success("remove", message, session=removed, cancelled=False))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_disable(rest, ctx):
    parsed = _parse_toggle_args(rest, "Usage: cdx disable <name> [--json]")
    session = ctx["service"]["set_session_enabled"](parsed["name"], False)
    message = f"Disabled session {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("disable", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_enable(rest, ctx):
    parsed = _parse_toggle_args(rest, "Usage: cdx enable <name> [--json]")
    session = ctx["service"]["set_session_enabled"](parsed["name"], True)
    message = f"Enabled session {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("enable", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0
