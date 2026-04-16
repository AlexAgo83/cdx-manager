import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CLAUDE_STATUS_PROBE_MODEL = os.environ.get("CDX_CLAUDE_STATUS_MODEL", "claude-haiku-4-5-20251001")


def _read_claude_credentials(auth_home):
    cred_path = os.path.join(auth_home, ".claude", ".credentials.json")
    try:
        with open(cred_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("claudeAiOauth")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _format_reset_date(unix_seconds):
    dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc).astimezone()
    return f"{MONTH_ABBR[dt.month - 1]} {dt.day} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}"


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
            "x-api-key": access_token,
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


def refresh_claude_session_status(session):
    creds = _read_claude_credentials(session.get("authHome", ""))
    if not creds or not creds.get("accessToken"):
        return None
    return fetch_claude_rate_limit_headers(creds["accessToken"])
