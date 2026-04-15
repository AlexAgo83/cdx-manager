import inspect
import threading
from datetime import datetime, timezone

from .claude_usage import refresh_claude_session_status
from .errors import CdxError

CLAUDE_REFRESH_TTL_SECONDS = 10 * 60


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_stale(session, now=None, ttl_seconds=CLAUDE_REFRESH_TTL_SECONDS):
    status = session.get("lastStatus") or {}
    updated_at = _parse_timestamp(status.get("updated_at") or session.get("lastStatusAt"))
    if not updated_at:
        return True
    now = now or datetime.now(timezone.utc).astimezone()
    return (now - updated_at.astimezone(now.tzinfo)).total_seconds() >= ttl_seconds


def _refresh_claude_sessions(service, refresh_fn=None, target_names=None, force=False, ttl_seconds=CLAUDE_REFRESH_TTL_SECONDS):
    refresh_fn = refresh_fn or refresh_claude_session_status
    target_names = set(target_names or [])
    sessions = service["list_sessions"]()
    claude_sessions = [
        s for s in sessions
        if s["provider"] == "claude"
        and (not target_names or s["name"] in target_names)
        and (force or _is_stale(s, ttl_seconds=ttl_seconds))
    ]
    if not claude_sessions:
        return {"refreshed": [], "errors": []}

    errors = []
    results = {}
    threads = []

    def fetch(s):
        try:
            usage = refresh_fn(s)
            if inspect.isawaitable(usage):
                import asyncio
                usage = asyncio.run(usage)
            if usage:
                results[s["name"]] = usage
        except Exception as e:
            errors.append({"session": s["name"], "error": e})

    for s in claude_sessions:
        t = threading.Thread(target=fetch, args=(s,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    for name, usage in results.items():
        try:
            service["record_status"](name, usage)
        except CdxError:
            errors.append({"session": name, "error": CdxError(f"Failed to record Claude status for {name}")})
    return {"refreshed": sorted(results), "errors": errors}
