"""Is a tray companion running, and which one.

The companion owns the lock; this only reads it. Both sides must agree on the
path, which is why the rule is written in one sentence in both places: the
per-user temporary directory, then `cdx-tray/companion.pid`.
"""
import os
import platform
import subprocess
import tempfile


def lock_path(env=None):
    env = os.environ if env is None else env
    if platform.system() == "Windows":
        base = env.get("LOCALAPPDATA") or tempfile.gettempdir()
    else:
        base = env.get("TMPDIR") or tempfile.gettempdir()
    return os.path.join(base, "cdx-tray", "companion.pid")


def _is_alive(pid):
    if platform.system() == "Windows":
        result = subprocess.run(
            ["tasklist", "/fi", f"PID eq {pid}", "/nh"],
            capture_output=True, text=True, check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        # Alive, owned by someone else. Still a reason not to start a second.
        return True
    return True


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
