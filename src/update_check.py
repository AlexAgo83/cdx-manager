import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone

UPDATE_CHECK_TTL_SECONDS = 60 * 60
LATEST_RELEASE_URL = "https://api.github.com/repos/AlexAgo83/cdx-manager/releases/latest"
LOGICS_MANAGER_LATEST_URL = "https://registry.npmjs.org/@grifhinz%2Flogics-manager/latest"


class LatestReleaseCheckError(Exception):
    pass


def _parse_version(value):
    raw = str(value or "").strip().lstrip("v")
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return None


def _is_newer_version(current_version, latest_version):
    current = _parse_version(current_version)
    latest = _parse_version(latest_version)
    if not current or not latest:
        return False
    return latest > current


def is_newer_version(current_version, latest_version):
    return _is_newer_version(current_version, latest_version)


def _cache_path(base_dir):
    return os.path.join(base_dir, "state", "update-check.json")


def _tool_cache_path(base_dir, tool):
    return os.path.join(base_dir, "state", f"{tool}-update-check.json")


def _read_cache(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _write_cache(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _github_token(env=None):
    env = env or os.environ
    return env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")


def _fetch_latest_release(env=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cdx-manager-update-check",
    }
    token = _github_token(env)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {
        "latest_version": str(payload.get("tag_name") or "").lstrip("v"),
        "url": payload.get("html_url") or payload.get("url"),
    }


def _format_fetch_error(error):
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 403:
            return (
                "GitHub API rate limit reached while checking the latest cdx-manager release. "
                "Try again later, set GH_TOKEN or GITHUB_TOKEN, or run cdx update --version <version>."
            )
        if error.code == 404:
            return "Unable to find the latest cdx-manager release on GitHub."
        return f"GitHub returned HTTP {error.code} while checking the latest cdx-manager release."
    if isinstance(error, urllib.error.URLError):
        reason = getattr(error, "reason", None)
        suffix = f" ({reason})" if reason else ""
        return f"Unable to reach GitHub while checking the latest cdx-manager release{suffix}."
    if isinstance(error, TimeoutError):
        return "Timed out while checking the latest cdx-manager release."
    return "Unable to check for the latest cdx-manager release."


def fetch_latest_release(env=None):
    try:
        return _fetch_latest_release(env=env)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _fetch_latest_npm_package_version(url=LOGICS_MANAGER_LATEST_URL):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "cdx-manager-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=1) as response:
        payload = json.loads(response.read().decode("utf-8"))
    version = payload.get("version") if isinstance(payload, dict) else None
    return str(version).strip() if version else None


def fetch_latest_logics_manager_version(env=None):
    try:
        return _fetch_latest_npm_package_version()
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _installed_logics_manager_version(env=None, runner=None):
    env = env or os.environ
    executable = shutil.which("logics-manager", path=env.get("PATH", ""))
    if not executable:
        return None
    runner = runner or subprocess.run
    try:
        result = runner(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=2,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if getattr(result, "returncode", 0) not in (0, None):
        return None
    output = (getattr(result, "stdout", "") or getattr(result, "stderr", "") or "").strip()
    parts = output.split()
    return parts[-1].lstrip("v") if parts else None


def fetch_latest_release_or_raise(env=None):
    try:
        return _fetch_latest_release(env=env)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
        raise LatestReleaseCheckError(_format_fetch_error(error)) from error


def check_for_update(base_dir, current_version, env=None, now_fn=None):
    env = env or os.environ
    now_fn = now_fn or (lambda: datetime.now(timezone.utc).timestamp())
    if env.get("CDX_DISABLE_UPDATE_CHECK") in {"1", "true", "TRUE", "yes", "YES"}:
        return None

    path = _cache_path(base_dir)
    now_ts = float(now_fn())
    cached = _read_cache(path) or {}
    checked_at = cached.get("checked_at")
    if isinstance(checked_at, (int, float)) and (now_ts - checked_at) < UPDATE_CHECK_TTL_SECONDS:
        latest_version = cached.get("latest_version")
        if _is_newer_version(current_version, latest_version):
            return {
                "latest_version": latest_version,
                "url": cached.get("url"),
                "cached": True,
            }
        return None

    latest = fetch_latest_release(env=env)
    if not latest:
        return None

    payload = {
        "checked_at": now_ts,
        "latest_version": latest.get("latest_version"),
        "url": latest.get("url"),
    }
    try:
        _write_cache(path, payload)
    except OSError:
        pass

    if _is_newer_version(current_version, latest.get("latest_version")):
        return {
            "latest_version": latest.get("latest_version"),
            "url": latest.get("url"),
            "cached": False,
        }
    return None


def check_logics_manager_for_update(base_dir, env=None, now_fn=None, runner=None):
    env = env or os.environ
    now_fn = now_fn or (lambda: datetime.now(timezone.utc).timestamp())
    if env.get("CDX_DISABLE_UPDATE_CHECK") in {"1", "true", "TRUE", "yes", "YES"}:
        return None
    if env.get("LOGICS_MANAGER_NO_UPDATE_CHECK") in {"1", "true", "TRUE", "yes", "YES"}:
        return None

    current_version = _installed_logics_manager_version(env=env, runner=runner)
    if not current_version:
        return None

    path = _tool_cache_path(base_dir, "logics-manager")
    now_ts = float(now_fn())
    cached = _read_cache(path) or {}
    checked_at = cached.get("checked_at")
    if isinstance(checked_at, (int, float)) and (now_ts - checked_at) < UPDATE_CHECK_TTL_SECONDS:
        latest_version = cached.get("latest_version")
        if _is_newer_version(current_version, latest_version):
            return {
                "tool": "logics-manager",
                "latest_version": latest_version,
                "current_version": current_version,
                "update_command": "logics-manager self-update",
                "url": cached.get("url"),
                "cached": True,
            }
        return None

    latest_version = fetch_latest_logics_manager_version(env=env)
    payload = {
        "checked_at": now_ts,
        "latest_version": latest_version,
        "url": "https://www.npmjs.com/package/@grifhinz/logics-manager",
    }
    try:
        _write_cache(path, payload)
    except OSError:
        pass

    if _is_newer_version(current_version, latest_version):
        return {
            "tool": "logics-manager",
            "latest_version": latest_version,
            "current_version": current_version,
            "update_command": "logics-manager self-update",
            "url": payload["url"],
            "cached": False,
        }
    return None
