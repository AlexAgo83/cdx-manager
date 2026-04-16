import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone


UPDATE_CHECK_TTL_SECONDS = 12 * 60 * 60
LATEST_RELEASE_URL = "https://api.github.com/repos/AlexAgo83/cdx-manager/releases/latest"


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


def _cache_path(base_dir):
    return os.path.join(base_dir, "state", "update-check.json")


def _read_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _write_cache(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _fetch_latest_release():
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "cdx-manager-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {
        "latest_version": str(payload.get("tag_name") or "").lstrip("v"),
        "url": payload.get("html_url") or payload.get("url"),
    }


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

    try:
        latest = _fetch_latest_release()
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
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
