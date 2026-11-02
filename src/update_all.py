"""Inventory and apply the safe, known updates for a CDX workstation."""

import json
import os
import platform
import re
import shutil
import subprocess
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA

_TOOLS = (
    (PROVIDER_CODEX, "codex"),
    (PROVIDER_CLAUDE, "claude"),
    (PROVIDER_ANTIGRAVITY, "agy"),
    (PROVIDER_OLLAMA, "ollama"),
    ("rtk", "rtk"),
)
_SOURCE_TIMEOUT = 5
_ANTIGRAVITY_RELEASES = "https://antigravity-auto-updater-974169037036.us-central1.run.app/releases"
_PONYTAIL_URL = "https://github.com/DietrichGebert/ponytail.git"


def _which(command, env):
    path = env.get("PATH")
    resolved = shutil.which(command, path=path)
    if resolved or not path:
        return resolved
    for directory in path.split(os.pathsep):
        candidate = os.path.join(directory, command)
        if os.path.isfile(candidate):
            return candidate
    return None


def _run(command, env, runner=None, timeout=15):
    runner = runner or subprocess.run
    try:
        result = runner(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"returncode": 1, "stdout": "", "stderr": str(error)}
    if isinstance(result, dict):
        return result
    return {"returncode": result.returncode, "stdout": result.stdout or "", "stderr": result.stderr or ""}


def _parse_version(value):
    if isinstance(value, str) and re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", value):
        return value.lstrip("v")
    return None


def _version(command, env, runner):
    result = _run([command, "--version"], env, runner, timeout=_SOURCE_TIMEOUT)
    if result["returncode"]:
        return None
    text = (result["stdout"] or result["stderr"] or "").strip()
    # Ollama can print the server version before the CLI version.
    client = re.search(r"client version is (\S+)", text)
    match = client or re.search(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b", text)
    return _parse_version(match.group(1)) if match else None


def _fetch_json(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "cdx-manager-update-check"})
    with urlopen(request, timeout=_SOURCE_TIMEOUT) as response:
        return json.loads(response.read(1024 * 1024))


def _latest_version(name):
    try:
        if name in (PROVIDER_CODEX, PROVIDER_CLAUDE):
            package = "@openai/codex" if name == PROVIDER_CODEX else "@anthropic-ai/claude-code"
            return _parse_version(_fetch_json(f"https://registry.npmjs.org/{package}/latest")["version"])
        if name == "rtk":
            release = _fetch_json("https://api.github.com/repos/rtk-ai/rtk/releases/latest")
            if release.get("draft") or release.get("prerelease"):
                return None
            return _parse_version(release["tag_name"])
        if name == PROVIDER_ANTIGRAVITY:
            # agy belongs to the original editor, whose feed differs from Hub and IDE 2.
            return _parse_version(_fetch_json(_ANTIGRAVITY_RELEASES)[0]["version"])
        if name == PROVIDER_OLLAMA:
            arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
            query = urlencode({"os": platform.system().lower(), "arch": arch, "version": "0.0.0"})
            release = _fetch_json(f"https://ollama.com/api/update?{query}")
            # The vendor updater extracts the release tag from the artifact URL.
            return _parse_version(os.path.basename(os.path.dirname(urlparse(release["url"]).path)))
    except Exception:
        # A failed or changed source is uncertainty, never evidence of currency.
        return None
    return None


def _newer(latest, current):
    def key(value):
        return tuple(int(part) for part in value.split("-", 1)[0].split("+", 1)[0].split("."))
    return bool(latest and current and key(latest) > key(current))


def _native_update_command(name, command, path, env, runner):
    real_path = os.path.realpath(path)
    cask = re.search(r"/Caskroom/([^/]+)/", real_path)
    formula = re.search(r"/Cellar/([^/]+)/", real_path)
    if (cask or formula) and _which("brew", env):
        package = (cask or formula).group(1)
        return ["brew", "upgrade", *(["--cask"] if cask else []), package]
    if name == PROVIDER_CODEX:
        return [command, "update"]
    help_result = _run([command, "--help"], env, runner, timeout=_SOURCE_TIMEOUT)
    if help_result["returncode"] == 0:
        help_text = help_result["stdout"]
        for subcommand in ("self-update", "update", "--update"):
            if re.search(r"(?m)^\s*" + re.escape(subcommand) + r"(?:\s|$)", help_text):
                return [command, subcommand]
    return None


def _ponytail_revision(auth_home, env=None, runner=None):
    try:
        with open(os.path.join(auth_home, "config.toml"), encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        text = ""
    match = re.search(r'\[marketplaces\.ponytail\].*?last_revision\s*=\s*"([0-9a-f]+)"', text, re.S)
    if match:
        return match.group(1)
    cache = os.path.join(auth_home, ".tmp", "marketplaces", "ponytail")
    result = _run(["git", "-C", cache, "rev-parse", "HEAD"], env or os.environ, runner)
    revision = (result["stdout"] or "").strip()
    return revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None


def collect_update_all_plan(service, env=None, runner=None):
    env = dict(env or os.environ)
    items, steps = [], []
    for name, command in _TOOLS:
        path = _which(command, env)
        current = _version(command, env, runner) if path else None
        item = {"name": name, "command": command, "installed": bool(path), "path": path,
                "version": current, "latest_version": None, "update_command": None, "status": "not_installed"}
        if path:
            latest = _latest_version(name)
            item["latest_version"] = latest
            if latest and current and latest == current:
                item["status"] = "up_to_date"
            elif _newer(latest, current):
                item["status"] = "update_available"
                item["update_command"] = _native_update_command(name, command, path, env, runner)
                if item["update_command"]:
                    steps.append({"name": name, "command": item["update_command"], "env": {}})
                else:
                    item["reason"] = "No supported CLI updater or verified Homebrew installation; use the vendor's updater manually."
            else:
                item["status"] = "unknown"
                item["reason"] = "Latest version unavailable from the official source." if not latest else "Installed version unavailable or does not match the published release."
        items.append(item)

    rtk_available = any(item["name"] == "rtk" and item["installed"] for item in items)
    missing_rtk = [session["name"] for session in service["list_sessions"]() if not (session.get("launch") or {}).get("rtk")]
    setup = {"rtk_available": rtk_available, "rtk_missing_sessions": missing_rtk, "ponytail": []}
    if rtk_available and missing_rtk:
        steps.append({"name": "enable RTK", "command": None, "sessions": missing_rtk})

    codex_sessions = [session for session in service["list_sessions"]() if session.get("provider") == PROVIDER_CODEX]
    ponytail_head = None
    if any(_ponytail_revision(session.get("authHome") or "", env, runner) for session in codex_sessions):
        remote = _run(["git", "ls-remote", _PONYTAIL_URL, "HEAD"], env, runner)
        candidate = (remote["stdout"] or "").split("\t", 1)[0].strip()
        ponytail_head = candidate if remote["returncode"] == 0 and re.fullmatch(r"[0-9a-f]{40}", candidate) else None
    for session in codex_sessions:
        revision = _ponytail_revision(session.get("authHome") or "", env, runner)
        row = {"session": session["name"], "installed": bool(revision), "revision": revision}
        if revision:
            row["latest_revision"] = ponytail_head
            row["status"] = "update_available" if ponytail_head and not ponytail_head.startswith(revision) else "up_to_date" if ponytail_head else "unknown"
            if row["status"] == "update_available":
                steps.append({"name": f"update Ponytail ({session['name']})", "command": ["codex", "plugin", "marketplace", "upgrade", "ponytail", "--json"], "env": {"CODEX_HOME": session["authHome"]}})
        else:
            row["status"] = "not_installed"
            marketplace_id = f"ponytail-marketplace:{session['name']}"
            steps.extend([
                {"id": marketplace_id, "name": f"add Ponytail marketplace ({session['name']})", "command": ["codex", "plugin", "marketplace", "add", _PONYTAIL_URL], "env": {"CODEX_HOME": session["authHome"]}},
                {"name": f"install Ponytail ({session['name']})", "command": ["codex", "plugin", "add", "ponytail@ponytail", "--json"], "env": {"CODEX_HOME": session["authHome"]}, "requires": marketplace_id},
            ])
        setup["ponytail"].append(row)
    return {"items": items, "setup": setup, "steps": steps}


def apply_update_all_plan(plan, service, env=None, runner=None, progress=None):
    env = dict(env or os.environ)
    results = []
    completed = set()
    for index, step in enumerate(plan["steps"], start=1):
        if progress:
            progress({"phase": "start", "index": index, "total": len(plan["steps"]), "step": step})
        if step.get("requires") and step["requires"] not in completed:
            result = {"name": step["name"], "returncode": None, "skipped": True, "blocked_by": step["requires"]}
            results.append(result)
            if progress:
                progress({"phase": "done", "index": index, "total": len(plan["steps"]), "step": step, "result": result})
            continue
        if step["command"] is None:
            for name in step["sessions"]:
                service["set_launch_settings"](name, {"rtk": True})
            result = {"name": step["name"], "returncode": 0, "sessions": step["sessions"]}
            results.append(result)
            if step.get("id"):
                completed.add(step["id"])
            if progress:
                progress({"phase": "done", "index": index, "total": len(plan["steps"]), "step": step, "result": result})
            continue
        result = _run(step["command"], {**env, **step.get("env", {})}, runner, timeout=120)
        result = {"name": step["name"], "command": step["command"], **result}
        results.append(result)
        if result["returncode"] == 0 and step.get("id"):
            completed.add(step["id"])
        if progress:
            progress({"phase": "done", "index": index, "total": len(plan["steps"]), "step": step, "result": result})
    return results
