"""What the desktop can actually do for the tray, read at the moment asked.

Two capabilities decide whether the companion's output ever reaches a person,
and both fail silently when absent, which is why `cdx tray doctor` has to name
them rather than leave the user to notice nothing happening:

  - Windows shows a toast from a non-packaged program only when a Start Menu
    shortcut carrying its AppUserModelID exists. Without one the notification
    API succeeds and nothing appears. A success code and no toast is the worst
    kind of failure to debug from the outside.
  - Linux draws a tray icon only where something owns the
    `org.kde.StatusNotifierWatcher` name. A desktop without it is not broken,
    it simply has no system tray, and saying so beats a companion that appears
    to start and then cannot be seen.

Nothing here repairs anything, and nothing runs unbounded: every probe is local
and time-limited, because a diagnostic that hangs is worse than one that admits
it does not know.
"""
import os
import platform
import subprocess

# Matches the identifier the companion registers with, and the name a user would
# recognise in the Start Menu. Both have to agree for a toast to be delivered.
SHORTCUT_NAME = "CDX.lnk"
PROBE_TIMEOUT_SECONDS = 3


def shortcut_path(env=None):
    """Where Windows looks for the shortcut, or None off Windows."""
    env = os.environ if env is None else env
    appdata = (env.get("APPDATA") or "").strip()
    if not appdata:
        return None
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", SHORTCUT_NAME)


def toast_capability(env=None, system=None):
    """Whether a toast raised by the companion could actually be shown.

    Only Windows makes this conditional. Elsewhere the answer is "nothing stands
    in the way", which is reported as such rather than as a pass on a check that
    was never run.
    """
    system = platform.system() if system is None else system
    if system != "Windows":
        return {
            "supported": True,
            "gated": False,
            "present": True,
            "path": None,
            "detail": "no Start Menu shortcut is required on this platform",
        }
    path = shortcut_path(env)
    if not path:
        return {
            "supported": True,
            "gated": True,
            "present": False,
            "path": None,
            "detail": "APPDATA is unset, so the Start Menu location cannot be resolved",
        }
    present = os.path.isfile(path)
    return {
        "supported": True,
        "gated": True,
        "present": present,
        "path": path,
        "detail": path if present else f"missing: {path}. Toasts are dropped silently without it",
    }


def desktop_capability(env=None, system=None, run=None):
    """Whether this desktop can draw a tray icon at all.

    macOS and Windows always can. Linux depends on a StatusNotifierItem watcher,
    which is a property of the running session rather than of the distribution,
    so it is resolved by asking the bus and never by matching a name.
    """
    system = platform.system() if system is None else system
    if system in ("Darwin", "Windows"):
        return {"available": True, "detail": "native tray"}

    env = os.environ if env is None else env
    if not (env.get("DBUS_SESSION_BUS_ADDRESS") or "").strip():
        return {"available": False, "detail": "no D-Bus session bus: this is not a desktop session"}

    runner = run or _run_dbus_send
    try:
        names = runner()
    except Exception:  # noqa: BLE001 - a diagnostic never propagates a failure
        return {"available": None, "detail": "could not query the session bus"}
    if names is None:
        return {"available": None, "detail": "could not query the session bus"}
    if "org.kde.StatusNotifierWatcher" in names:
        return {"available": True, "detail": "StatusNotifierItem watcher present"}
    return {
        "available": False,
        "detail": "no org.kde.StatusNotifierWatcher: this desktop has no system tray. "
                  "On GNOME, install the AppIndicator extension",
    }


def _run_dbus_send():
    """The same question the Linux backend asks, asked the same way."""
    try:
        completed = subprocess.run(
            [
                "dbus-send", "--session", "--dest=org.freedesktop.DBus",
                "--type=method_call", "--print-reply", "/org/freedesktop/DBus",
                "org.freedesktop.DBus.ListNames",
            ],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout
