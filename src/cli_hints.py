"""One-line setup hints, shown only while they are still actionable.

CDX has optional surfaces a user cannot discover by reading the output of the
command they already run: agent alerts, and the tray companion. A hint is how
they learn, so the bar is that it must be worth interrupting for.

Four rules keep it from becoming noise, and each exists because the obvious
version of this feature fails without it:

  - Never in `--json`. That is a contract, and a helpful line inside it is a
    parse error somewhere else.
  - At most one per invocation, and not again for six hours. Advice that repeats
    on every command stops being read, including the day it matters.
  - Retired after three showings. A user who saw it three times and did not act
    has answered; asking a fourth time is nagging, not helping.
  - Silent on any failure. A hint is the least important thing on the screen,
    so it never breaks, slows, or interrupts the command that carried it.

Every condition is answered from local state already on disk. Nothing here
probes a provider, touches the network, or costs a measurable amount of time.
"""
import json
import os
import time

HINT_STATE_VERSION = 1
# Long enough that a burst of commands shows nothing, short enough that a hint
# still reaches someone who uses CDX a few times a day.
QUIET_SECONDS = 6 * 60 * 60
MAX_SHOWINGS = 3


def _state_path(base_dir):
    return os.path.join(base_dir, "hints.json")


def _read_state(base_dir):
    """What was shown and when. A damaged file reads as empty, never as an error."""
    try:
        with open(_state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {"version": HINT_STATE_VERSION, "hints": {}}
    if not isinstance(state, dict) or state.get("version") != HINT_STATE_VERSION:
        return {"version": HINT_STATE_VERSION, "hints": {}}
    if not isinstance(state.get("hints"), dict):
        state["hints"] = {}
    return state


def _write_state(base_dir, state):
    try:
        os.makedirs(base_dir, exist_ok=True)
        with open(_state_path(base_dir), "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
    except OSError:
        # Unwritable state means hints repeat rather than disappear. That is the
        # right way to fail: a lost preference is better than a lost command.
        pass


def _tray_installed(base_dir, env):
    if (env.get("CDX_TRAY_BIN") or "").strip():
        return True
    try:
        from .tray_install import read_state as read_install_state
        return bool(read_install_state(base_dir))
    except Exception:  # noqa: BLE001 - a hint never propagates a failure
        return False


def _autostart_on(env):
    try:
        from .tray_autostart import status as autostart_status
        return bool(autostart_status(env=env).get("enabled"))
    except Exception:  # noqa: BLE001
        return False


def _alerts_on(sessions):
    return any(
        session.get("notify") and session.get("enabled", True) is not False
        for session in sessions
    )


def available_hints(base_dir, env, sessions):
    """Every hint that is true right now, most useful first.

    Ordered rather than scored: the tray is worth more than its autostart, and
    both are worth more than nothing to alert about. A user with no sessions is
    told nothing at all, because every hint here presumes there is something to
    watch.
    """
    if not sessions:
        return []

    hints = []
    installed = _tray_installed(base_dir, env)
    if not installed:
        hints.append((
            "tray_not_installed",
            "Did you know? A menu bar icon can watch your quota. Run: cdx tray install",
        ))
    elif not _autostart_on(env):
        hints.append((
            "tray_autostart_off",
            "Did you know? The tray can start with your session. Run: cdx tray autostart on",
        ))
    if not _alerts_on(sessions):
        hints.append((
            "agent_alerts_off",
            "Did you know? CDX can notify you when an agent finishes. Run: cdx set <name> --notify on",
        ))
    return hints


def next_hint(base_dir, env, sessions, now=None):
    """The one hint to show, or None. Records the showing when it returns one."""
    if (env.get("CDX_NO_HINTS") or "").strip():
        return None

    now = time.time() if now is None else now
    state = _read_state(base_dir)
    seen = state["hints"]

    # "Never shown" is its own case, not a showing at the Unix epoch. Treating
    # the two alike silences the very first hint, which is the one that matters.
    shown_at = [entry["last"] for entry in seen.values() if isinstance(entry, dict) and entry.get("last")]
    if shown_at and now - max(shown_at) < QUIET_SECONDS:
        return None

    for code, message in available_hints(base_dir, env, sessions):
        entry = seen.get(code) if isinstance(seen.get(code), dict) else {}
        if entry.get("shown", 0) >= MAX_SHOWINGS:
            continue
        seen[code] = {"shown": entry.get("shown", 0) + 1, "last": now}
        _write_state(base_dir, state)
        return message
    return None


def write_hint(ctx):
    """Print one hint after the command's own output. Never raises.

    Yields to an update notice. Both want the last line, and one of them is
    actionable news about the tool the user is running while the other is
    optional discovery — so they never stack, and the hint waits for a quieter
    run rather than pushing the notice up out of the eye's landing spot.
    """
    try:
        if ctx.get("update_notices"):
            return
        env = ctx.get("env")
        env = os.environ if env is None else env
        service = ctx.get("service") or {}
        base_dir = service.get("base_dir")
        if not base_dir:
            return
        sessions = service["list_sessions"]()
        message = next_hint(base_dir, env, sessions)
        if not message:
            return
        from .cli_render import _dim
        ctx["out"](f"{_dim(message, ctx.get('use_color', False))}\n")
    except Exception:  # noqa: BLE001 - deliberate: a hint must never break a command
        pass
