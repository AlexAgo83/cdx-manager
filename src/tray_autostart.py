"""Start the tray companion at login, or do not. Explicitly, either way.

`req_038` AC1 is the whole design here: installing must never enable startup,
and turning it on must be a separate, reversible, idempotent act that reports
what the platform actually holds rather than what CDX last intended.

One recorded artifact per platform, chosen for being the plainest thing that can
be deleted again: a LaunchAgent plist, the per-user Run key, an XDG autostart
entry. All three are per-user and need no administrator rights.
"""
import os
import platform
import plistlib
import subprocess

LABEL = "com.cdx.tray"
RUN_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "CDXTray"


def _home(env):
    return env.get("HOME") or os.path.expanduser("~")


def artifact_path(env=None, system=None):
    """Where this platform records "start at login", or None if unsupported."""
    env = os.environ if env is None else env
    system = system or platform.system()
    if system == "Darwin":
        return os.path.join(_home(env), "Library", "LaunchAgents", f"{LABEL}.plist")
    if system == "Linux":
        base = env.get("XDG_CONFIG_HOME") or os.path.join(_home(env), ".config")
        return os.path.join(base, "autostart", "cdx-tray.desktop")
    if system == "Windows":
        # Not a path: the registry value is the artifact. Named so callers can
        # report it, and so uninstall knows what to remove.
        return f"{RUN_KEY}\\{RUN_VALUE}"
    return None


def status(env=None, system=None, run=None):
    """What the platform holds right now, read back rather than remembered.

    Reading the real state is the point: a recorded intention that drifted from
    the system is exactly the confusion `cdx tray doctor` exists to end.
    """
    env = os.environ if env is None else env
    system = system or platform.system()
    path = artifact_path(env=env, system=system)
    if not path:
        return {"supported": False, "enabled": False, "artifact": None}
    if system == "Windows":
        runner = run or _run
        result = runner(["reg", "query", RUN_KEY, "/v", RUN_VALUE])
        return {"supported": True, "enabled": result.returncode == 0, "artifact": path}
    return {"supported": True, "enabled": os.path.exists(path), "artifact": path}


def _run(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


def enable(executable, env=None, system=None, run=None):
    """Idempotent by construction: writing the same artifact twice is a no-op."""
    env = os.environ if env is None else env
    system = system or platform.system()
    path = artifact_path(env=env, system=system)
    if not path:
        raise NotImplementedError(f"No autostart mechanism for {system}.")
    if system == "Windows":
        runner = run or _run
        runner(["reg", "add", RUN_KEY, "/v", RUN_VALUE, "/t", "REG_SZ", "/d", executable, "/f"])
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if system == "Darwin":
        with open(path, "wb") as handle:
            plistlib.dump({
                "Label": LABEL,
                "ProgramArguments": [executable],
                "RunAtLoad": True,
                # No KeepAlive: quitting the tray from its own menu must mean
                # quit, not "be restarted immediately by launchd".
                "KeepAlive": False,
            }, handle)
    else:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "[Desktop Entry]\nType=Application\nName=CDX Tray\n"
                f"Exec={executable}\nX-GNOME-Autostart-enabled=true\n"
            )
    return path


def disable(env=None, system=None, run=None):
    """Remove the artifact. Absent is success, not an error."""
    env = os.environ if env is None else env
    system = system or platform.system()
    path = artifact_path(env=env, system=system)
    if not path:
        return False
    if system == "Windows":
        runner = run or _run
        result = runner(["reg", "delete", RUN_KEY, "/v", RUN_VALUE, "/f"])
        return result.returncode == 0
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
