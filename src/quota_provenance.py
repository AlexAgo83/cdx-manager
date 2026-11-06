"""Additive quota evidence; never infer a measurement from a missing value."""

from datetime import datetime, timezone

SOURCES = {"codex_rate_limits", "claude_probe", "claude_statusline", "cache", "unknown"}


def quota_windows(status, provider, reason=None, now=None):
    status = status or {}
    now = now or datetime.now(timezone.utc)
    ttl = {"codex": 300, "claude": 600}.get(provider, 60)
    source = {
        "api:codex-app-server-rate-limits": "codex_rate_limits",
        "api:anthropic-ratelimit-headers": "claude_probe",
        "claude:statusline": "claude_statusline",
    }.get(status.get("source_ref"), "cache")
    windows = {}
    for name, field in (("5h", "remaining_5h_pct"), ("weekly", "remaining_week_pct")):
        evidence = (status.get("quota_windows") or {}).get(name, {})
        value = status.get(field)
        observed_at = evidence.get("observed_at", status.get("updated_at")) if value is not None else None
        try:
            observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            observed_at = observed.isoformat()
        except (TypeError, ValueError):
            observed, observed_at = None, None
        window_reason = reason or ("missing_window" if value is None else None)
        availability = "unavailable" if window_reason else "measured"
        if not window_reason and (observed is None or (now - observed).total_seconds() >= ttl):
            availability = "stale"
        window_source = evidence.get("source", source) if value is not None else "unknown"
        windows[name] = {
            "source": window_source if window_source in SOURCES else "unknown",
            "observed_at": observed_at,
            "availability": availability,
            "reason": window_reason,
        }
    return windows


def mark_quota_unavailable(row, reason):
    for window in row.get("quota_windows", {}).values():
        window.update(availability="unavailable", reason=reason)
