import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

from .errors import CdxError

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CLAUDE_STATUS_PROBE_MODEL = os.environ.get("CDX_CLAUDE_STATUS_MODEL", "claude-haiku-4-5-20251001")
CLAUDE_AUTH_STATUS_TIMEOUT_SECONDS = 15


def _read_claude_credentials(auth_home):
    cred_path = os.path.join(auth_home, ".claude", ".credentials.json")
    try:
        with open(cred_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("claudeAiOauth")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _home_env_overrides(auth_home):
    overrides = {"HOME": auth_home, "CLAUDE_CONFIG_DIR": auth_home}
    if sys.platform == "win32":
        overrides["USERPROFILE"] = auth_home
        overrides["HOMEDRIVE"] = os.path.splitdrive(auth_home)[0] or "C:"
        overrides["HOMEPATH"] = os.path.splitdrive(auth_home)[1] or auth_home
    return overrides


def _refresh_claude_cli_credentials(auth_home, runner=None, env=None):
    if not auth_home:
        return
    if os.environ.get("CDX_CLAUDE_SKIP_AUTH_STATUS_REFRESH") == "1":
        return
    runner = runner or subprocess.run
    command = ["claude", "auth", "status"]
    run_env = {**(env or os.environ), **_home_env_overrides(auth_home)}
    try:
        runner(
            command,
            env=run_env,
            capture_output=True,
            text=True,
            timeout=CLAUDE_AUTH_STATUS_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return


def _format_reset_date(unix_seconds):
    dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc).astimezone()
    return f"{MONTH_ABBR[dt.month - 1]} {dt.day} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}"


def _read_http_error_message(error):
    try:
        body = error.read().decode("utf-8", errors="replace")
    except (AttributeError, OSError, UnicodeDecodeError):
        body = ""
    if not body:
        return ""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body.strip()
    detail = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("type")
        if message:
            return str(message)
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("detail")
        if message:
            return str(message)
    return body.strip()


def fetch_claude_rate_limit_headers(access_token):
    body = json.dumps({
        "model": CLAUDE_STATUS_PROBE_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            headers = {k.lower(): v for k, v in resp.getheaders()}
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in e.headers.items()}
        if (
            "anthropic-ratelimit-unified-5h-utilization" not in headers
            and "anthropic-ratelimit-unified-7d-utilization" not in headers
        ):
            message = _read_http_error_message(e)
            suffix = f": {message}" if message else ""
            raise CdxError(f"Claude usage unavailable (HTTP {e.code}{suffix})") from e
    except urllib.error.URLError:
        return None

    util_5h = headers.get("anthropic-ratelimit-unified-5h-utilization")
    reset_5h = headers.get("anthropic-ratelimit-unified-5h-reset")
    util_7d = headers.get("anthropic-ratelimit-unified-7d-utilization")
    reset_7d = headers.get("anthropic-ratelimit-unified-7d-reset")

    if util_5h is None and util_7d is None:
        return None

    utilization_5h = float(util_5h) if util_5h is not None else None
    utilization_7d = float(util_7d) if util_7d is not None else None

    reset_5h_at = _format_reset_date(int(reset_5h)) if reset_5h else None
    reset_week_at = _format_reset_date(int(reset_7d)) if reset_7d else None
    reset_at = reset_week_at or reset_5h_at

    return {
        "remaining_5h_pct": round((1 - utilization_5h) * 100) if utilization_5h is not None else None,
        "remaining_week_pct": round((1 - utilization_7d) * 100) if utilization_7d is not None else None,
        "reset_5h_at": reset_5h_at,
        "reset_week_at": reset_week_at,
        "reset_at": reset_at,
        "updated_at": datetime.now().astimezone().isoformat(),
        "raw_status_text": None,
        "source_ref": "api:anthropic-ratelimit-headers",
    }


def refresh_claude_session_status(session, auth_refresher=None):
    auth_home = session.get("authHome", "")
    refresher = auth_refresher or _refresh_claude_cli_credentials
    refresher(auth_home)
    creds = _read_claude_credentials(auth_home)
    if not creds or not creds.get("accessToken"):
        return None
    return fetch_claude_rate_limit_headers(creds["accessToken"])
