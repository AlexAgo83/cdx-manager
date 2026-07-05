import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .errors import CdxError

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CLAUDE_STATUS_PROBE_MODEL = os.environ.get("CDX_CLAUDE_STATUS_MODEL", "claude-haiku-4-5-20251001")
CLAUDE_AUTH_STATUS_TIMEOUT_SECONDS = 15


class ClaudeAuthInvalidError(CdxError):
    pass


def _clean_oauth_token(token):
    if not token:
        return None
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", str(token)).strip()
    if not text or text.startswith("<") or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        return None
    return text


def _decode_jwt_claims(token):
    if not token or "." not in str(token):
        return {}
    parts = str(token).split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _read_claude_credentials(auth_home):
    cred_path = os.path.join(auth_home, ".claude", ".credentials.json")
    try:
        with open(cred_path, encoding="utf-8") as f:
            data = json.load(f)
        creds = data.get("claudeAiOauth") if isinstance(data, dict) else None
        token = _clean_oauth_token(creds.get("accessToken")) if isinstance(creds, dict) else None
        if token:
            return {**creds, "accessToken": token}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    anthropic_cred_path = os.path.join(auth_home, "credentials", "default.json")
    try:
        with open(anthropic_cred_path, encoding="utf-8") as f:
            data = json.load(f)
        token = _clean_oauth_token(data.get("access_token") if isinstance(data, dict) else None)
        if token:
            return {"accessToken": token}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def _home_env_overrides(auth_home):
    overrides = {
        "HOME": auth_home,
        "ANTHROPIC_CONFIG_DIR": auth_home,
        "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS": "1",
    }
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
    try:
        dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc).astimezone()
    except (TypeError, ValueError, OSError):
        return None
    return f"{MONTH_ABBR[dt.month - 1]} {dt.day} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}"


def _parse_reset_epoch(value):
    # The reset headers are unix seconds today, but an RFC3339 value must
    # not abort the whole refresh.
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _remaining_from_utilization(value):
    if value is None:
        return None
    try:
        return max(0, min(100, round((1 - float(value)) * 100)))
    except (TypeError, ValueError):
        return None


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
        if e.code == 401:
            message = _read_http_error_message(e)
            suffix = f": {message}" if message else ""
            raise ClaudeAuthInvalidError(f"Claude usage unavailable (HTTP {e.code}{suffix})") from e
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

    utilization_5h = _safe_float(util_5h)
    utilization_7d = _safe_float(util_7d)

    reset_5h_at = _format_reset_date(_parse_reset_epoch(reset_5h)) if reset_5h else None
    reset_week_at = _format_reset_date(_parse_reset_epoch(reset_7d)) if reset_7d else None
    reset_at = reset_week_at or reset_5h_at

    return {
        "remaining_5h_pct": _remaining_from_utilization(utilization_5h),
        "remaining_week_pct": _remaining_from_utilization(utilization_7d),
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
