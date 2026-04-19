import os
import subprocess
import sys
from pathlib import Path

from .errors import CdxError


def _package_root(path=None):
    if path is not None:
        return Path(path).resolve()
    return Path(__file__).resolve().parents[1]


def _normalize_version(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lstrip("v")


def _is_standalone_install(package_root):
    return package_root.parent.name == "versions"


def _is_source_checkout(package_root):
    return (package_root / ".git").exists()


def _is_git_dirty(package_root):
    try:
        result = subprocess.run(
            ["git", "-C", str(package_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise CdxError("git is required to update a source checkout.") from error
    return bool((result.stdout or "").strip())


def _is_python_env(prefix=None, base_prefix=None):
    prefix = prefix or sys.prefix
    base_prefix = base_prefix or sys.base_prefix
    return prefix != base_prefix


def detect_installation(package_root=None, prefix=None, base_prefix=None):
    root = _package_root(package_root)
    if _is_standalone_install(root):
        return {"mode": "standalone", "package_root": str(root)}
    if _is_source_checkout(root):
        return {"mode": "source", "package_root": str(root)}
    if _is_python_env(prefix=prefix, base_prefix=base_prefix):
        return {"mode": "python", "package_root": str(root)}
    if (root / "package.json").exists():
        return {"mode": "npm", "package_root": str(root)}
    return {"mode": "unknown", "package_root": str(root)}


def _join_command(*parts):
    return [str(part) for part in parts if part is not None]


def _build_standalone_step(package_root, target_version):
    package_root = _package_root(package_root)
    env = {}
    if target_version:
        env["CDX_VERSION"] = target_version
    if sys.platform == "win32":
        return {
            "label": "standalone installer",
            "command": _join_command("powershell", "-ExecutionPolicy", "Bypass", "-File", package_root / "install.ps1"),
            "cwd": str(package_root),
            "env": env,
        }
    return {
        "label": "standalone installer",
        "command": _join_command("sh", package_root / "install.sh"),
        "cwd": str(package_root),
        "env": env,
    }


def _build_source_steps(package_root, target_version):
    package_root = _package_root(package_root)
    if _is_git_dirty(package_root):
        raise CdxError(
            "Your source checkout has uncommitted changes. "
            "Commit or stash them before running cdx update."
        )
    if target_version:
        return [
            {
                "label": "fetch tags",
                "command": _join_command("git", "-C", package_root, "fetch", "--tags", "--force"),
                "cwd": str(package_root),
                "env": {},
            },
            {
                "label": f"checkout v{target_version}",
                "command": _join_command("git", "-C", package_root, "checkout", f"v{target_version}"),
                "cwd": str(package_root),
                "env": {},
            },
        ]
    return [
        {
            "label": "git pull --ff-only",
            "command": _join_command("git", "-C", package_root, "pull", "--ff-only"),
            "cwd": str(package_root),
            "env": {},
        }
    ]


def _build_python_step(target_version):
    command = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if target_version:
        command.append(f"cdx-manager=={target_version}")
    else:
        command.append("cdx-manager")
    return {
        "label": "python package upgrade",
        "command": command,
        "cwd": None,
        "env": {},
    }


def _build_npm_step(target_version):
    spec = f"cdx-manager@{target_version}" if target_version else "cdx-manager@latest"
    return {
        "label": "npm global upgrade",
        "command": ["npm", "install", "-g", spec],
        "cwd": None,
        "env": {},
    }


def build_update_plan(target_version=None, package_root=None, env=None, prefix=None, base_prefix=None):
    root = _package_root(package_root)
    version = _normalize_version(target_version)
    detection = detect_installation(root, prefix=prefix, base_prefix=base_prefix)
    mode = detection["mode"]
    if mode == "standalone":
        steps = [_build_standalone_step(root, version)]
    elif mode == "source":
        steps = _build_source_steps(root, version)
    elif mode == "python":
        steps = [_build_python_step(version)]
    elif mode == "npm":
        steps = [_build_npm_step(version)]
    else:
        raise CdxError(
            "Unable to determine how cdx-manager was installed. "
            "Set CDX_UPDATE_METHOD or update it manually."
        )
    return {
        "mode": mode,
        "package_root": str(root),
        "target_version": version,
        "steps": steps,
    }


def _result_code(result):
    if isinstance(result, dict):
        return result.get("returncode") if result.get("returncode") is not None else result.get("status")
    return getattr(result, "returncode", getattr(result, "status", None))


def _result_text(result, attr):
    if isinstance(result, dict):
        return result.get(attr)
    return getattr(result, attr, "")


def run_update_plan(plan, runner=None, env=None):
    runner = runner or subprocess.run
    results = []
    for step in plan["steps"]:
        step_env = {**(env or os.environ), **(step.get("env") or {})}
        kwargs = {"cwd": step.get("cwd"), "env": step_env, "check": False}
        result = runner(step["command"], **kwargs)
        code = _result_code(result)
        results.append({
            "label": step["label"],
            "command": step["command"],
            "cwd": step.get("cwd"),
            "returncode": code,
            "stdout": _result_text(result, "stdout"),
            "stderr": _result_text(result, "stderr"),
        })
        if code not in (0, None):
            break
    return results


def format_update_failure(results):
    if not results:
        return "Update failed."
    last = results[-1]
    message = last.get("stderr") or last.get("stdout") or "Update failed."
    return f"{last['label']} failed: {str(message).strip()}"
