import shutil
import subprocess


LOGICS_MANAGER_INSTALL_HINT = "Install or update it with: npm install -g @grifhinz/logics-manager"


def resolve_logics_manager(env=None):
    env = env or {}
    return shutil.which("logics-manager", path=env.get("PATH", ""))


def build_viewer_diagnostics(executable, cwd, update_notice=None, failure=None):
    command = [executable or "logics-manager", "view"]
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


def run_logics_viewer(executable, cwd, env=None, runner=None):
    runner = runner or subprocess.run
    argv = [executable, "view"]
    if runner is subprocess.run:
        return subprocess.run(argv, cwd=cwd, env=env)
    return runner(argv, cwd=cwd, env=env)
