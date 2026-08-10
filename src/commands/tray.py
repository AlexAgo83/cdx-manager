"""Tray domain commands: the `cdx tray` surface a companion talks to.

This slice owns the contract, not the companion. `status` is fully implemented
because it is what the native process reads; `install`, `launch`, and
`uninstall` are declared here with non-mutating behaviour so the surface is
stable and discoverable before any binary exists. They report that honestly
rather than pretending to do something.
"""
from datetime import datetime, timezone

from ..cli_args import TRAY_USAGE, _parse_flag_args
from ..cli_helpers import _json_success, _write_json
from ..cli_render import _dim, _pad_table, _style, _warn
from ..errors import CdxError
from ..tray_contract import (
    AUTH_LOCKED,
    FRESH,
    UNKNOWN,
    build_snapshot,
)

TRAY_ACTIONS = ("status", "install", "launch", "uninstall")

# Reported by install/launch/uninstall until item_080 ships a companion. A code
# rather than prose so a caller can branch on it.
COMPANION_UNAVAILABLE = "tray_companion_not_available"

_FRESHNESS_TEXT = {
    FRESH: "fresh",
    AUTH_LOCKED: "cannot refresh while the session runs",
    UNKNOWN: "never reported",
}


def handle_tray(rest, ctx):
    if not rest or rest[0] in ("help", "--help", "-h"):
        ctx["out"](f"{TRAY_USAGE}\n")
        return 0
    action, *args = rest
    if action not in TRAY_ACTIONS:
        raise CdxError(TRAY_USAGE)
    if action == "status":
        return _tray_status(args, ctx)
    return _companion_action(action, args, ctx)


def _tray_status(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)

    # Cached by default: a tray polls, and a live probe would contend on the
    # Codex auth lock and can invalidate a rotating refresh token. Only an
    # explicit refresh, which is a user gesture from the menu, may probe.
    rows = ctx["service"]["get_status_rows"](
        force_refresh=parsed["refresh"],
        cache_only=not parsed["refresh"],
    )
    snapshot = build_snapshot(
        rows,
        datetime.now(timezone.utc),
        ctx["version"],
        refreshable=not any(row.get("active") for row in rows),
    )
    if parsed["json"]:
        _write_json(ctx, _json_success("tray.status", "Built tray snapshot", snapshot=snapshot))
        return 0
    ctx["out"](f"{_format_snapshot(snapshot, use_color=ctx['use_color'])}\n")
    return 0


def _companion_action(action, args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    message = (
        f"cdx tray {action} is defined but no tray companion ships with CDX {ctx['version']}. "
        "Nothing was installed, started, or changed."
    )
    if parsed["json"]:
        _write_json(ctx, _json_success(
            f"tray.{action}",
            message,
            warnings=[{"code": COMPANION_UNAVAILABLE, "message": message}],
            applied=False,
        ))
        return 0
    ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
    return 0


def _pct(value):
    return "?" if value is None else f"{int(value)}%"


def _format_snapshot(snapshot, use_color=False):
    icon = snapshot["icon"]
    header = _style(f"tray: {icon['state']}", "1", use_color)
    if not snapshot["sessions"]:
        return f"{header}\n{_dim('No enabled sessions.', use_color)}"
    rows = [["SESSION", "PROVIDER", "LEFT", "STATE", "DATA"]]
    for session in snapshot["sessions"]:
        rows.append([
            session["name"] or "?",
            session["provider"] or "-",
            _pct(session["available_pct"]),
            session["state"],
            _FRESHNESS_TEXT.get(session["freshness"], session["freshness"]),
        ])
    lines = [header, _pad_table(rows)]
    if not snapshot["refreshable"]:
        lines.append(_dim("A running session holds the provider lock; refresh will not update it.", use_color))
    return "\n".join(lines)
