"""What a newly created session inherits, once the user has said yes once.

Accepting agent alerts during `cdx tray install` has to mean two different
things, and only saying one of them is what made the feature feel broken: the
sessions that exist today get alerts, and the ones created tomorrow get them
too. Without the second, a user who accepted alerts finds their next session
silent and has no reason to suspect a per-session opt-in they never saw.

Stored beside the mute state rather than in the session file, because it is not
a property of any session: it is the answer to a question asked once, and a
session created later has to be able to read it.
"""
import json
import os

STATE_VERSION = 1


def state_path(base_dir):
    return os.path.join(base_dir, "tray", "defaults.json")


def alerts_default(base_dir):
    """Whether a new supported session starts with alerts on.

    Off unless explicitly accepted. Anything unreadable, unrecognised or from a
    version this build does not know reads as off: inheriting an opt-in from a
    file we cannot understand would enable provider hooks nobody agreed to.
    """
    try:
        with open(state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return False
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        return False
    return state.get("notify") is True


def set_alerts_default(base_dir, enabled):
    """Record the answer, and report what it now is."""
    path = state_path(base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump({"version": STATE_VERSION, "notify": bool(enabled)}, handle, indent=2)
    os.replace(temp, path)
    return bool(enabled)
