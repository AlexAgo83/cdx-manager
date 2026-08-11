"""Whether agent alerts may raise a banner right now.

A quick way to go quiet during a meeting or a screen share, and back afterwards,
without touching the per-session `--notify` preferences — those say which
sessions may alert at all, and losing them to a temporary mute would be a poor
trade for two minutes of silence.

Two decisions are worth stating because they are what make it a *silence*:

  - Muting stops the banner, not the recording. Events keep arriving in the
    tray's recent list, so the menu is where you catch up on what you missed.
    An switch that dropped them would be an off, not a mute.
  - It applies to the direct notification path too, not only to a running tray.
    Otherwise quitting the companion would silently un-mute you, which is
    exactly the kind of surprise a mute exists to prevent.

Stored in CDX's own home rather than in the companion, because the hook is what
reads it and the hook is not the tray.
"""
import json
import os

STATE_VERSION = 1


def state_path(base_dir):
    return os.path.join(base_dir, "tray", "alerts.json")


def alerts_enabled(base_dir):
    """On unless explicitly muted.

    Anything unreadable or unrecognised reads as on. A mute that outlived a
    damaged file would silence someone with no way to see why, and silence is
    the failure that hides itself.
    """
    try:
        with open(state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return True
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        return True
    return state.get("enabled") is not False


def set_alerts(base_dir, enabled):
    """Mute or unmute, and report what it now is."""
    path = state_path(base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump({"version": STATE_VERSION, "enabled": bool(enabled)}, handle, indent=2)
    os.replace(temp, path)
    return bool(enabled)
