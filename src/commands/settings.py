"""Launch settings domain commands: set, unset, and the power/perm/fast/model aliases.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

from ..agent_notify import supports_agent_alerts
from ..cli_args import _parse_launch_setting_alias_args, _parse_set_args, _parse_unset_args
from ..cli_helpers import _format_launch_config, _json_success, _write_json
from ..cli_render import _success
from ..errors import CdxError


def _resolve_bulk_launch_targets(parsed, service):
    sessions = service["list_sessions"]()
    by_name = {session["name"]: session for session in sessions}
    if parsed.get("name"):
        session = by_name.get(parsed["name"])
        if not session:
            raise CdxError(f"Unknown session: {parsed['name']}")
        targets = [session]
    elif parsed.get("sessions") == "all":
        targets = sessions
    elif parsed.get("sessions"):
        targets = []
        for name in parsed["sessions"]:
            session = by_name.get(name)
            if not session:
                raise CdxError(f"Unknown session: {name}")
            targets.append(session)
    else:
        targets = sessions
    if parsed.get("provider"):
        targets = [session for session in targets if session["provider"] == parsed["provider"]]
    if not targets:
        raise CdxError("No sessions matched.")
    return targets

def _format_bulk_launch_summary(sessions):
    names = [session["name"] for session in sessions]
    if len(names) <= 8:
        return ", ".join(names)
    return ", ".join(names[:8]) + f", +{len(names) - 8} more"


def _notification_setting_notice(settings, sessions, action):
    if "notify" in settings:
        supported = [session for session in sessions if supports_agent_alerts(session["provider"])]
        unsupported = [session for session in sessions if not supports_agent_alerts(session["provider"])]
        notices = []
        if supported:
            names = _format_bulk_launch_summary(supported)
            if action == "set" and settings["notify"]:
                notices.append(f"Agent alerts enabled for {names} — hooks install on the next interactive launch.")
            else:
                notices.append(f"Agent alerts disabled for {names} — cdx removes its hooks on the next interactive launch.")
        if unsupported:
            names = _format_bulk_launch_summary(unsupported)
            notices.append(f"Agent alerts updated for {names} — this provider does not support notification hooks.")
        return "\n".join(notices)
    if "notify_preview" in settings:
        names = _format_bulk_launch_summary(sessions)
        if action == "set" and settings["notify_preview"]:
            return f"Response previews enabled for {names} — completion text may be visible on the lock screen."
        return f"Response previews disabled for {names}."
    return None

def _apply_launch_settings(parsed, ctx, action="set"):
    targets = _resolve_bulk_launch_targets(parsed, ctx["service"])
    sessions = [
        ctx["service"]["set_launch_settings"](session["name"], parsed["settings"])
        for session in targets
    ]
    if len(sessions) == 1:
        session = sessions[0]
        message = f"Updated launch settings for {session['name']}"
    else:
        message = f"Updated launch settings for {len(sessions)} sessions: {_format_bulk_launch_summary(sessions)}"
    if parsed["json"]:
        payload = _json_success(
            action,
            message,
            updated_count=len(sessions),
            session=sessions[0] if len(sessions) == 1 else None,
            sessions=sessions,
            launch=sessions[0].get("launch") or {} if len(sessions) == 1 else None,
        )
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    notice = _notification_setting_notice(parsed["settings"], sessions, action)
    if notice:
        ctx["out"](f"{notice}\n")
    if len(sessions) == 1:
        ctx["out"](f"{_format_launch_config(sessions[0], ctx['use_color'])}\n")
    return 0

def _clear_launch_settings(parsed, ctx, action="unset"):
    targets = _resolve_bulk_launch_targets(parsed, ctx["service"])
    sessions = [
        ctx["service"]["unset_launch_settings"](session["name"], parsed["keys"])
        for session in targets
    ]
    if len(sessions) == 1:
        session = sessions[0]
        message = f"Cleared launch settings for {session['name']}"
    else:
        message = f"Cleared launch settings for {len(sessions)} sessions: {_format_bulk_launch_summary(sessions)}"
    if parsed["json"]:
        payload = _json_success(
            action,
            message,
            updated_count=len(sessions),
            session=sessions[0] if len(sessions) == 1 else None,
            sessions=sessions,
            launch=sessions[0].get("launch") or {} if len(sessions) == 1 else None,
        )
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    notice = _notification_setting_notice({key: False for key in parsed["keys"]}, sessions, action)
    if notice:
        ctx["out"](f"{notice}\n")
    if len(sessions) == 1:
        ctx["out"](f"{_format_launch_config(sessions[0], ctx['use_color'])}\n")
    return 0

def handle_set(rest, ctx):
    return _apply_launch_settings(_parse_set_args(rest), ctx)

def handle_unset(rest, ctx):
    return _clear_launch_settings(_parse_unset_args(rest), ctx)

def handle_launch_setting_alias(kind, rest, ctx):
    parsed = _parse_launch_setting_alias_args(kind, rest)
    if parsed.get("settings"):
        return _apply_launch_settings(parsed, ctx, action=kind)
    return _clear_launch_settings(parsed, ctx, action=kind)
