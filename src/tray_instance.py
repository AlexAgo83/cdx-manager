"""Is a tray companion running, and which one.

The companion owns the lock; this only reads it. Both sides must agree on the
path, which is why the rule is written in one sentence in both places: the
per-user directory (LOCALAPPDATA on Windows, TMPDIR on macOS, XDG_RUNTIME_DIR on
Linux, else the temp dir with the uid in the folder name), then
`cdx-tray/companion.pid`.
"""
import os
import platform
import tempfile

from .session_helpers import _process_is_running


def lock_path(env=None):
    env = os.environ if env is None else env
    system = platform.system()
    if system == "Windows":
        base = env.get("LOCALAPPDATA") or tempfile.gettempdir()
    elif system == "Linux":
        # /tmp is shared on Linux: one user's lock would block another's tray.
        if env.get("XDG_RUNTIME_DIR"):
            return os.path.join(env["XDG_RUNTIME_DIR"], "cdx-tray", "companion.pid")
        base = env.get("TMPDIR") or tempfile.gettempdir()
        return os.path.join(base, f"cdx-tray-{os.getuid()}", "companion.pid")
    else:
        base = env.get("TMPDIR") or tempfile.gettempdir()
    return os.path.join(base, "cdx-tray", "companion.pid")


def _is_alive(pid):
    # Alive includes owned by someone else: still a reason not to start a second.
    return _process_is_running(pid)


def companion_instance(env=None):
    """`pid` when one is running, and whether a stale lock is lying around.

    A stale lock is worth reporting rather than hiding: it is the visible trace
    of a companion that crashed, and the next launch reclaims it.
    """
    path = lock_path(env=env)
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read().strip()
    except OSError:
        return {"pid": None, "stale": False, "lock": path}
    try:
        pid = int(raw)
    except ValueError:
        return {"pid": None, "stale": True, "lock": path}
    if _is_alive(pid):
        return {"pid": pid, "stale": False, "lock": path}
    return {"pid": None, "stale": True, "lock": path}
