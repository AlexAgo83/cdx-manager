"""Replacing a companion that is currently running.

`cdx update` used to leave the running tray on its old binary and tell the user
to quit it from its menu. That is a correct thing to say and a poor thing to
have to do: the whole point of the companion is that nobody thinks about it.

The order here is what makes it safe, and it is the reverse of what looks
natural. The running companion is asked to stop *before* anything on disk moves,
so the replacement never has to fight a live process for its own files — on
Windows a running executable cannot be replaced at all, and a directory holding
one cannot reliably be renamed either. Stop, replace, start, and if the start
fails, put back the one that was proven to work and start that instead.

Nothing here kills anything. A companion that does not stop within the bounded
wait is left alone and reported, because a tray the user is reading a menu from
is not a process to terminate over a version number.
"""
import os
import time

from .tray_instance import _is_alive, companion_instance, lock_path

# How long to wait for a companion to notice the request and exit.
#
# It polls several times a second, so this is generous by two orders of
# magnitude — deliberately. On Windows the menu is modal: while the user has it
# open, the message pump is stopped and the companion notices nothing at all.
# Ten seconds covers reading a menu and closing it; beyond that, the honest
# answer is to leave it running and say so.
STOP_TIMEOUT_SECONDS = 10.0
_POLL_SECONDS = 0.1


def stop_path(env=None):
    """Where a stop request is written. Beside the lock, by the same rule."""
    return os.path.join(os.path.dirname(lock_path(env=env)), "companion.stop")


def request_stop(env=None):
    """Ask the running companion to exit. False when it could not be asked."""
    path = stop_path(env=env)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("stop")
        return True
    except OSError:
        return False


def clear_stop(env=None):
    """Remove a stop request nobody consumed.

    A companion that had already died leaves the request on disk, and the next
    one to start would read it and quit immediately — a tray that refuses to
    stay open, with nothing on screen explaining why.
    """
    try:
        os.remove(stop_path(env=env))
    except OSError:
        pass


def wait_for_exit(pid, timeout=STOP_TIMEOUT_SECONDS, sleep=None, alive=None):
    """Wait for one process to go, up to `timeout`. True if it did."""
    sleep = time.sleep if sleep is None else sleep
    alive = _is_alive if alive is None else alive
    deadline = time.monotonic() + timeout
    while True:
        if not alive(pid):
            return True
        if time.monotonic() >= deadline:
            return False
        sleep(_POLL_SECONDS)


def stop_running_companion(env=None, timeout=STOP_TIMEOUT_SECONDS, sleep=None, alive=None):
    """Stop the companion if one is running, and say what happened.

    `stopped` is True only when a live companion was asked and observed to go.
    Everything else is a reason, and every reason is one the caller can act on
    without guessing: nothing was running, the request could not be written, or
    it did not exit in time.
    """
    instance = companion_instance(env=env)
    pid = instance.get("pid")
    if not pid:
        # A stale lock is not a running tray, but it is worth clearing the stop
        # request that may be sitting beside it from an earlier attempt.
        clear_stop(env=env)
        return {"stopped": False, "was_running": False, "reason": "no tray companion is running"}
    if not request_stop(env=env):
        return {
            "stopped": False,
            "was_running": True,
            "pid": pid,
            "reason": "the stop request could not be written",
        }
    if not wait_for_exit(pid, timeout=timeout, sleep=sleep, alive=alive):
        # It is still running and it still owns its binary. Withdrawing the
        # request matters: leaving it would stop the companion later, at a
        # moment nobody connected to an update.
        clear_stop(env=env)
        return {
            "stopped": False,
            "was_running": True,
            "pid": pid,
            "reason": (
                f"the running tray did not stop within {timeout:g}s. "
                "An open tray menu blocks it on Windows; close the menu and run: cdx tray launch"
            ),
        }
    clear_stop(env=env)
    return {"stopped": True, "was_running": True, "pid": pid}


def start_companion(executable, spawn=None, verify=None, env=None, settle=None):
    """Start a companion and confirm it is actually running.

    Spawning is not evidence. A binary that exits immediately — a missing
    library, a quarantined bundle, a companion that reads a stale stop request —
    leaves a successful spawn and no tray, which is exactly the "reported
    success before the replacement is usable" this must not do.
    """
    from .tray_install import launch_command

    spawn = spawn or _spawn_detached
    settle = time.sleep if settle is None else settle
    try:
        spawn(launch_command(executable))
    except Exception as error:  # noqa: BLE001 - any launch failure is a reason
        return {"started": False, "reason": str(error)}
    # It has to register its lock before it counts as running, and it does that
    # a moment after exec.
    for _ in range(20):
        settle(_POLL_SECONDS)
        instance = (verify or companion_instance)(env=env)
        if instance.get("pid"):
            return {"started": True, "pid": instance["pid"]}
    return {"started": False, "reason": "it was launched but never registered as running"}


def _spawn_detached(command):
    import subprocess

    subprocess.Popen(  # noqa: S603  (path comes from our own install state)
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
