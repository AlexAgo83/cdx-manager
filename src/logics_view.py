import os
import shutil
import subprocess

LOGICS_MANAGER_INSTALL_HINT = "Install or update it with: npm install -g @grifhinz/logics-manager"


def resolve_logics_manager(env=None):
    env = env or {}
    return shutil.which("logics-manager", path=env.get("PATH") or None)


def build_viewer_diagnostics(executable, cwd, update_notice=None, failure=None, extra_args=None):
    command = [executable or "logics-manager", "view"] + (extra_args or [])
    return {
        "available": bool(executable),
        "executable": executable,
        "command": command,
        "cwd": cwd,
        "update": update_notice,
        "failure": failure,
    }


def missing_logics_manager_failure():
    return {
        "code": "logics_manager_missing",
        "message": f"logics-manager is required for cdx view. {LOGICS_MANAGER_INSTALL_HINT}",
    }


def run_logics_viewer(executable, cwd, env=None, extra_args=None, runner=None):
    runner = runner or subprocess.run
    argv = [executable, "view"] + (extra_args or [])
    merged_env = {**os.environ, **(env or {})}
    if runner is subprocess.run:
        return subprocess.run(argv, cwd=cwd, env=merged_env)
    return runner(argv, cwd=cwd, env=merged_env)


def spawn_logics_viewer(executable, cwd, env=None, extra_args=None, runner=None):
    """Start the long-running viewer without making a tray click wait for it."""
    argv = [executable, "view"] + (extra_args or [])
    merged_env = {**os.environ, **(env or {})}
    return (runner or subprocess.Popen)(
        argv, cwd=cwd, env=merged_env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
