"""Where an installed tray companion lives, and what was recorded about it.

`cdx tray install` is item_081's job; this module owns the shape of what it
writes so `launch` and `uninstall` can already be truthful about a companion
that is or is not there. Uninstall must remove only what install recorded, so
the record is the contract, not a guess about where files might be.
"""
import json
import os
import platform

STATE_VERSION = 1

# Every path install writes goes in here, so removal never has to guess.
def state_dir(base_dir):
    return os.path.join(base_dir, "tray")


def state_path(base_dir):
    return os.path.join(state_dir(base_dir), "install.json")


def read_state(base_dir):
    """What install recorded, or None. A damaged record reads as absent.

    Refusing to parse rather than guessing is the safe failure here: the record
    drives deletion, and a half-understood one could remove the wrong path.
    """
    try:
        with open(state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        return None
    return state


def companion_path(base_dir, env=None):
    """The companion to launch, and where that answer came from.

    `CDX_TRAY_BIN` wins so a locally built companion can be run before any
    install path exists; that is how this was developed and tested.
    """
    env = os.environ if env is None else env
    override = (env.get("CDX_TRAY_BIN") or "").strip()
    if override:
        return override, "override"
    state = read_state(base_dir)
    if state and state.get("executable"):
        return state["executable"], "installed"
    return None, "absent"


def launch_command(executable):
    """How to start the companion without holding on to it.

    On macOS an installed companion is an app bundle, and `open` hands it to
    launchd so it survives this process exiting. A bare binary is spawned
    directly, which is what a development build is.
    """
    if platform.system() == "Darwin" and executable.endswith(".app"):
        return ["open", "-a", executable]
    return [executable]
