"""Which terminal a tray session row opens.

The companion picks one per platform today: Terminal.app on macOS, the first of
four names that answers on Linux. Someone who works in iTerm or Ghostty gets a
second terminal application opened beside the one they were already in, which is
the opposite of the shortcut the row is meant to be.

What is stored is an application, never a command, and that restriction is the
whole security argument. A preference that could hold a command line would be a
way to run anything, in a process the user did not start, triggered by clicking
a menu row — and it would be writable by anything that can write CDX's state.
The validation below is what makes "open my terminal" impossible to turn into
"run this". Nothing here reaches a shell: the value names an application and the
platform's own launcher resolves it.
"""
import json
import os
import re
import shutil
import subprocess
import sys

STATE_VERSION = 1
SORT_VALUES = ("capacity", "reset", "recent")
# An application name or a bundle identifier, and nothing that could be read as
# a command. No slashes, so it cannot name a path; no quotes, semicolons,
# ampersands, pipes, backticks or dollars, so it cannot carry a shell fragment;
# it must start with a letter or a digit, so it cannot be read as a flag.
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")

REFUSAL = (
    "A terminal preference is an application name, not a command: "
    "letters, digits, spaces, dots, dashes and underscores only. "
    'Examples: "iTerm", "Ghostty", "WezTerm", "kitty", "wt".'
)


def state_path(base_dir):
    return os.path.join(base_dir, "tray", "terminal.json")


def terminal_preference(base_dir):
    """The chosen terminal, or None for the platform's default.

    Anything unreadable, unrecognised, or no longer valid reads as no
    preference. A value that fails validation today must not be honoured just
    because it was written before the rule existed.
    """
    state = _state(base_dir)
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        return None
    name = state.get("terminal")
    return name if isinstance(name, str) and _NAME.match(name) else None


def sort_preference(base_dir):
    state = _state(base_dir)
    value = state.get("sort")
    return value if value in SORT_VALUES else "capacity"


def valid_terminal(name):
    return isinstance(name, str) and bool(_NAME.match(name))


def terminal_candidates(platform=None, which=None, available=None):
    """Known launchable applications on this host; no guessed executables."""
    platform = platform or sys.platform
    which = which or shutil.which
    names = ["Terminal", "iTerm", "Ghostty", "WezTerm"] if platform == "darwin" else (["wt", "powershell", "pwsh", "cmd"] if platform.startswith("win") else ["x-terminal-emulator", "gnome-terminal", "konsole", "xterm"])
    if platform == "darwin":
        available = available or (lambda name: subprocess.run(["open", "-Ra", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)
        return [name for name in names if available(name)]
    return [name for name in names if which(name)]


def set_terminal(base_dir, name):
    """Record a preferred terminal. Raises ValueError on anything else."""
    if not valid_terminal(name):
        raise ValueError(REFUSAL)
    state = _state(base_dir)
    state["terminal"] = name
    _write(base_dir, state)
    return name


def clear_terminal(base_dir):
    """Return to the platform's default."""
    state = _state(base_dir)
    state["terminal"] = None
    _write(base_dir, state)
    return None


def set_sort(base_dir, value):
    if value not in SORT_VALUES:
        raise ValueError("Tray sort must be capacity, reset, or recent.")
    state = _state(base_dir)
    state["sort"] = value
    _write(base_dir, state)
    return value


def _state(base_dir):
    try:
        with open(state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        state = {}
    return state if isinstance(state, dict) and state.get("version") == STATE_VERSION else {"version": STATE_VERSION}


def _write(base_dir, state):
    path = state_path(base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    os.replace(temp, path)
