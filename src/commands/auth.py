"""Authentication domain commands: login, logout, reset, ready.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import time
import uuid

from ..cli_args import _parse_flag_args, _parse_json_flag
from ..cli_helpers import (
    _bootstrap_claude_setup_token,
    _json_success,
    _local_now_iso,
    _make_notify_progress,
    _resolve_confirmation,
    _write_json,
)
from ..cli_render import _success, _warn
from ..codex_usage import consume_codex_rate_limit_reset_credit
from ..config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA
from ..errors import CdxError
from ..notify import (
    format_scheduled_notification,
    parse_ready_args,
    resolve_notify_event,
    schedule_notification_event,
    send_desktop_notification,
)
from ..provider_runtime import _ensure_session_authentication, _run_interactive_provider_command


def _confirm_reset(name):
    answer = input(f"Consume one banked Codex reset for {name}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")

def handle_ready(rest, ctx):
    """`cdx ready`: schedule an OS notification for the next session to come back.

    This is all that remains of the quota-reset flow: `cdx notify` now means
    agent notifications, and the wait-and-poll surface that used to sit here was
    unreachable once `cdx ready` became the only entry point.
    """
    parsed = parse_ready_args(rest)
    event = resolve_notify_event(
        ctx["service"]["get_status_rows"](
            progress_callback=None if parsed["json"] else _make_notify_progress(ctx),
            force_refresh=parsed["refresh"],
        ),
        parsed,
        (ctx["options"].get("now") or time.time)(),
    )
    if event["ready"]:
        send_desktop_notification(
            event["title"], event["message"],
            spawn_sync=ctx.get("spawn_sync"), env=ctx.get("env"),
        )
        schedule = {
            "scheduled": False,
            "backend": "immediate",
            "message": event["message"],
            "target_timestamp": event.get("target_timestamp"),
        }
    else:
        schedule = schedule_notification_event(
            ctx["service"]["base_dir"],
            parsed,
            event,
            spawn_sync=ctx.get("spawn_sync"),
            env=ctx.get("env"),
            now_fn=ctx["options"].get("now"),
        )
    if parsed["json"]:
        _write_json(ctx, _json_success("notify", "Scheduled notification event", event=event, schedule=schedule))
    else:
        ctx["out"](f"{format_scheduled_notification(schedule)}\n")
    return 0

def handle_reset(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--yes": {"key": "yes", "type": "bool", "default": False},
    }, "Usage: cdx reset <name> [--yes] [--json]", positionals_key="args", max_positionals=1)
    if len(parsed["args"]) != 1:
        raise CdxError("Usage: cdx reset <name> [--yes] [--json]")
    name = parsed["args"][0]
    session = ctx["service"]["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    if session["provider"] != PROVIDER_CODEX:
        raise CdxError("Banked rate-limit resets are only available for Codex sessions.")

    status = ctx["service"]["get_status_row"](name, force_refresh=True)
    if status.get("reset_credits_available") == 0:
        raise CdxError(f"No banked Codex reset is available for {name}.")
    if not parsed["yes"]:
        confirm_fn = ctx["options"].get("confirmReset")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, name)
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Reset activation requires an interactive terminal or --yes in non-interactive mode.")
        else:
            confirmed = _confirm_reset(name)
        if not confirmed:
            if parsed["json"]:
                _write_json(ctx, _json_success("reset", "Cancelled.", cancelled=True, session=name))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0

    credit_rows = status.get("reset_credits") or []
    credit_id = credit_rows[0].get("id") if credit_rows else None
    consumer = ctx["options"].get("consumeCodexReset") or consume_codex_rate_limit_reset_credit
    result = consumer(
        session,
        ctx["options"].get("resetIdempotencyKey") or str(uuid.uuid4()),
        credit_id=credit_id,
    )
    if not result.get("ok"):
        if result.get("reason") == "reset_consume_failed":
            raise CdxError(
                f"Unable to activate Codex reset for {name}. "
                "The installed Codex version or account may not support reset activation."
            )
        raise CdxError(f"Unable to activate Codex reset for {name}: {result.get('reason') or 'unknown error'}")
    outcome = result.get("outcome")
    if outcome == "noCredit":
        raise CdxError(f"No banked Codex reset is available for {name}.")
    if outcome == "nothingToReset":
        raise CdxError(f"No current Codex rate-limit window is eligible for reset on {name}.")
    if outcome not in ("reset", "alreadyRedeemed"):
        raise CdxError(f"Unexpected Codex reset outcome for {name}: {outcome or 'missing'}")
    refreshed = ctx["service"]["get_status_row"](name, force_refresh=True)
    message = f"Activated banked Codex reset for {name}"
    if parsed["json"]:
        _write_json(ctx, _json_success("reset", message, cancelled=False, outcome=outcome, session=refreshed))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_login(rest, ctx):
    rest = [arg for arg in rest if arg != "--setup-token"]  # accepted for back-compat; setup-token is now the default for Claude
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx login <name> [--json]")
    if not ctx["stdin_is_tty"]:
        raise CdxError("Login requires an interactive terminal.")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session["provider"] == PROVIDER_CLAUDE:
        # ponytail: setup-token mints a ~1yr token; claude login mints a ~daily one that forces reconnects
        _bootstrap_claude_setup_token(session, ctx)
    else:
        _run_interactive_provider_command(
            session, "login", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
            signal_emitter=ctx.get("signal_emitter")
        )
    auth_probe = _ensure_session_authentication(
        session,
        ctx["service"],
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
        behavior="probe-only",
        trust_local_credentials=False,
    )
    if not auth_probe.get("authenticated"):
        raise CdxError(
            f"Login command completed, but session {session['name']} is still not authenticated."
        )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](args[0], lambda auth: {
        **auth, "status": "authenticated",
        "lastCheckedAt": now, "lastAuthenticatedAt": now,
    })
    message = f"Reauthenticated session {session['name']} ({session['provider']})"
    if json_flag:
        _write_json(ctx, _json_success("login", message, session=ctx["service"]["get_session"](session["name"])))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0

def handle_logout(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx logout <name> [--json]")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session["provider"] == PROVIDER_ANTIGRAVITY:
        raise CdxError("Antigravity logout is managed inside agy. Launch the session and run /logout.")
    if session["provider"] == PROVIDER_OLLAMA:
        raise CdxError("Ollama sessions do not use cdx-managed authentication.")
    _run_interactive_provider_command(
        session, "logout", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter")
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](args[0], lambda auth: {
        **auth, "status": "logged_out",
        "lastCheckedAt": now, "lastLoggedOutAt": now,
    })
    message = f"Logged out session {session['name']} ({session['provider']})"
    if json_flag:
        _write_json(ctx, _json_success("logout", message, session=ctx["service"]["get_session"](session["name"])))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0
