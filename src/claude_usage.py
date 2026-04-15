import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _read_claude_credentials(auth_home):
    cred_path = os.path.join(auth_home, ".claude", ".credentials.json")
    try:
        with open(cred_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("claudeAiOauth")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _format_reset_date(unix_seconds):
    dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
    return f"{MONTH_ABBR[dt.month - 1]} {dt.day}"


def fetch_claude_rate_limit_headers(access_token):
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
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

    reset_ts = reset_7d or reset_5h
    reset_at = _format_reset_date(int(reset_ts)) if reset_ts else None

    return {
        "remaining_5h_pct": round((1 - utilization_5h) * 100) if utilization_5h is not None else None,
        "remaining_week_pct": round((1 - utilization_7d) * 100) if utilization_7d is not None else None,
        "reset_at": reset_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "raw_status_text": None,
        "source_ref": "api:anthropic-ratelimit-headers",
    }


def refresh_claude_session_status(session):
    creds = _read_claude_credentials(session.get("authHome", ""))
    if not creds or not creds.get("accessToken"):
        return None
    return fetch_claude_rate_limit_headers(creds["accessToken"])
