"""Inventory and apply the safe, known updates for a CDX workstation."""

import json
import os
import re
import shutil
import subprocess

from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA


_TOOLS = (
    (PROVIDER_CODEX, "codex", None, ["codex", "update"]),
    (PROVIDER_CLAUDE, "claude", "claude", ["brew", "upgrade", "--cask", "claude"]),
    (PROVIDER_ANTIGRAVITY, "agy", "antigravity", ["brew", "upgrade", "--cask", "antigravity"]),
    (PROVIDER_OLLAMA, "ollama", "ollama", ["brew", "upgrade", "ollama"]),
    ("rtk", "rtk", "rtk", ["brew", "upgrade", "rtk"]),
)
_PONYTAIL_URL = "https://github.com/DietrichGebert/ponytail.git"


def _run(command, env, runner=None, timeout=15):
    runner = runner or subprocess.run
    try:
        result = runner(command, env=env, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"returncode": 1, "stdout": "", "stderr": str(error)}
    if isinstance(result, dict):
        return result
    return {"returncode": result.returncode, "stdout": result.stdout or "", "stderr": result.stderr or ""}


def _version(command, env, runner):
    result = _run([command, "--version"], env, runner)
    text = (result["stdout"] or result["stderr"] or "").strip()
    match = re.search(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b", text)
    return match.group(1) if match else None


def _npm_latest(package, env, runner):
    if not shutil.which("npm", path=env.get("PATH")):
        return None
    result = _run(["npm", "view", package, "version"], env, runner)
    value = (result["stdout"] or "").strip()
    return value if re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", value) else None


def _newer(latest, current):
    def key(value):
        return tuple(int(part) for part in str(value).split("-", 1)[0].split("+", 1)[0].split("."))
    return bool(latest and current and key(latest) > key(current))


def _brew_outdated(env, runner):
    if not shutil.which("brew", path=env.get("PATH")):
        return {}
    result = _run(["brew", "outdated", "--json=v2"], env, runner, timeout=30)
    try:
        payload = json.loads(result["stdout"])
    except (TypeError, ValueError):
        return {}
    rows = {}
    for group in ("formulae", "casks"):
        for item in payload.get(group, []):
            rows[item.get("name")] = item
    return rows


def _ponytail_revision(auth_home):
    try:
        with open(os.path.join(auth_home, "config.toml"), encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    match = re.search(r'\[marketplaces\.ponytail\].*?last_revision\s*=\s*"([0-9a-f]+)"', text, re.S)
    return match.group(1) if match else None


def collect_update_all_plan(service, env=None, runner=None):
    env = dict(env or os.environ)
    outdated = _brew_outdated(env, runner)
    items, steps = [], []
    for name, command, brew_name, update_command in _TOOLS:
        path = shutil.which(command, path=env.get("PATH"))
        item = {"name": name, "command": command, "installed": bool(path), "path": path, "version": _version(command, env, runner) if path else None}
        brew_row = outdated.get(brew_name) if brew_name else None
        if brew_row:
            item.update({"status": "update_available", "latest_version": brew_row.get("current_version"), "update_command": update_command})
            steps.append({"name": name, "command": update_command, "env": {}})
        elif path and name == PROVIDER_CODEX:
            # Codex owns its installer; it is the only reliable updater across npm, Homebrew and standalone installs.
            latest = _npm_latest("@openai/codex", env, runner)
            item.update({"latest_version": latest, "status": "update_available" if _newer(latest, item["version"]) else "up_to_date" if latest else "check_with_native_updater", "update_command": update_command})
            if item["status"] != "up_to_date":
                steps.append({"name": name, "command": update_command, "env": {}})
        else:
            item["status"] = "up_to_date" if path else "not_installed"
        items.append(item)

    rtk_available = any(item["name"] == "rtk" and item["installed"] for item in items)
    missing_rtk = [session["name"] for session in service["list_sessions"]() if not (session.get("launch") or {}).get("rtk")]
    setup = {"rtk_available": rtk_available, "rtk_missing_sessions": missing_rtk, "ponytail": []}
    if rtk_available and missing_rtk:
        steps.append({"name": "enable RTK", "command": None, "sessions": missing_rtk})

    codex_sessions = [session for session in service["list_sessions"]() if session.get("provider") == PROVIDER_CODEX]
    ponytail_head = None
    if any(_ponytail_revision(session.get("authHome") or "") for session in codex_sessions):
        remote = _run(["git", "ls-remote", _PONYTAIL_URL, "HEAD"], env, runner)
        ponytail_head = (remote["stdout"] or "").split("\t", 1)[0].strip() or None
    for session in codex_sessions:
        revision = _ponytail_revision(session.get("authHome") or "")
        row = {"session": session["name"], "installed": bool(revision), "revision": revision}
        if revision:
            row["latest_revision"] = ponytail_head
            row["status"] = "update_available" if ponytail_head and not ponytail_head.startswith(revision) else "up_to_date"
            if row["status"] == "update_available":
                steps.append({"name": f"update Ponytail ({session['name']})", "command": ["codex", "plugin", "marketplace", "upgrade", "ponytail", "--json"], "env": {"CODEX_HOME": session["authHome"]}})
        else:
            row["status"] = "not_installed"
            steps.extend([
                {"name": f"add Ponytail marketplace ({session['name']})", "command": ["codex", "plugin", "marketplace", "add", "ponytail", _PONYTAIL_URL], "env": {"CODEX_HOME": session["authHome"]}},
                {"name": f"install Ponytail ({session['name']})", "command": ["codex", "plugin", "add", "ponytail@ponytail", "--json"], "env": {"CODEX_HOME": session["authHome"]}},
            ])
        setup["ponytail"].append(row)
    return {"items": items, "setup": setup, "steps": steps}


def apply_update_all_plan(plan, service, env=None, runner=None):
    env = dict(env or os.environ)
    results = []
    for step in plan["steps"]:
        if step["command"] is None:
            for name in step["sessions"]:
                service["set_launch_settings"](name, {"rtk": True})
            results.append({"name": step["name"], "returncode": 0, "sessions": step["sessions"]})
            continue
        result = _run(step["command"], {**env, **step.get("env", {})}, runner, timeout=120)
        results.append({"name": step["name"], "command": step["command"], **result})
    return results
