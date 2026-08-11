"""Status domain: reading, caching, merging and reporting session status.

Split out of session_service.py along one of the two seams the req_027
coupling measurement supports. Moved verbatim; re-exported by session_service.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .claude_usage import _decode_jwt_claims
from .config import PROVIDER_CLAUDE, PROVIDER_CODEX, get_cdx_home
from .errors import CdxError
from .session_helpers import (
    _get_global_codex_home,
    _get_session_auth_home,
    _local_now_iso,
    _session_runtime,
    list_sessions,
)
from .status_source import find_latest_status_artifact

STATUS_CACHE_TTL_SECONDS = 60

CLAUDE_STATUS_CACHE_TTL_SECONDS = 10 * 60

CODEX_STATUS_CACHE_TTL_SECONDS = 5 * 60

MAX_STATUS_WORKERS = 8

def _to_local_iso(value):
    if not value:
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().isoformat()

def _row_priority(session):
    launch = session.get("launch") or {}
    try:
        return int(launch.get("priority") or 0)
    except (TypeError, ValueError):
        return 0

def _row_reasoning_effort(session):
    launch = session.get("launch") or {}
    return (
        launch.get("reasoning_effort")
        or launch.get("reasoningEffort")
        or launch.get("power")
        or ("low" if launch.get("fast") is True and launch.get("fastMode") != "service_tier" else None)
        or "low"
    )

def _normalize_pct_value(value):
    if value is None:
        return None
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None

def _normalize_status_payload(payload=None):
    if payload is None:
        payload = {}
    now = _local_now_iso()
    return {
        "usage_pct": _normalize_pct_value(payload.get("usage_pct")),
        "remaining_5h_pct": _normalize_pct_value(payload.get("remaining_5h_pct")),
        "remaining_week_pct": _normalize_pct_value(payload.get("remaining_week_pct")),
        "credits": payload.get("credits"),
        "reset_credits_available": payload.get("reset_credits_available"),
        "reset_credits": payload.get("reset_credits"),
        "reset_5h_at": payload.get("reset_5h_at"),
        "reset_week_at": payload.get("reset_week_at"),
        "reset_at": payload.get("reset_at") or payload.get("reset_week_at") or payload.get("reset_5h_at"),
        "rate_limit_reached": payload.get("rate_limit_reached"),
        "updated_at": _to_local_iso(payload.get("updated_at") or payload.get("captured_at") or now),
        "raw_status_text": payload.get("raw_status_text"),
        "source_ref": payload.get("source_ref"),
        "structured": bool(payload.get("structured")),
    }

def _parse_status_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

def _status_cache_ttl_seconds(session, ttl_seconds=STATUS_CACHE_TTL_SECONDS):
    if ttl_seconds == STATUS_CACHE_TTL_SECONDS:
        if session.get("provider") == PROVIDER_CLAUDE:
            return CLAUDE_STATUS_CACHE_TTL_SECONDS
        if session.get("provider") == PROVIDER_CODEX:
            return CODEX_STATUS_CACHE_TTL_SECONDS
    return ttl_seconds

def _is_status_cache_fresh(session, ttl_seconds=STATUS_CACHE_TTL_SECONDS):
    status = session.get("lastStatus") or {}
    if _is_low_confidence_status_source(status):
        return False
    updated_at = _parse_status_timestamp(status.get("updated_at") or session.get("lastStatusAt"))
    if not updated_at:
        return False
    now = datetime.now(timezone.utc).astimezone()
    ttl_seconds = _status_cache_ttl_seconds(session, ttl_seconds)
    return (now - updated_at.astimezone(now.tzinfo)).total_seconds() < ttl_seconds

def _is_status_newer(candidate, current):
    if not candidate:
        return False
    if not current:
        return True
    candidate_at = _parse_status_timestamp(candidate.get("updated_at"))
    current_at = _parse_status_timestamp(current.get("updated_at"))
    if candidate_at and current_at:
        return candidate_at > current_at
    if candidate_at:
        return True
    return False

def _status_has_more_detail(candidate, current):
    if not candidate:
        return False
    if not current:
        return True

    fields = [
        "usage_pct",
        "remaining_5h_pct",
        "remaining_week_pct",
        "credits",
        "reset_credits_available",
        "reset_credits",
        "reset_5h_at",
        "reset_week_at",
        "reset_at",
        "raw_status_text",
        "source_ref",
    ]
    return any(current.get(field) is None and candidate.get(field) is not None for field in fields)

def _later_status_timestamp(current_at, candidate_at):
    if not candidate_at:
        return current_at
    if not current_at:
        return candidate_at
    parsed_current = _parse_status_timestamp(current_at)
    parsed_candidate = _parse_status_timestamp(candidate_at)
    if not parsed_current or not parsed_candidate:
        return current_at
    return candidate_at if parsed_candidate > parsed_current else current_at


def _merge_status_payload(current, candidate):
    if not current:
        return candidate
    if not candidate:
        return current

    merged = dict(current)
    for field in [
        "usage_pct",
        "remaining_5h_pct",
        "remaining_week_pct",
        "credits",
        "reset_credits_available",
        "reset_credits",
        "reset_5h_at",
        "reset_week_at",
        "reset_at",
        "raw_status_text",
        "source_ref",
    ]:
        if merged.get(field) is None and candidate.get(field) is not None:
            merged[field] = candidate[field]

    # The structured marker qualifies the source_ref; keep them in sync when
    # the merge adopts the candidate's ref, else a structured rollout ref
    # would read as low-confidence scraped text.
    if merged.get("source_ref") is not None and merged["source_ref"] == candidate.get("source_ref"):
        merged["structured"] = bool(candidate.get("structured"))

    # The merge is only reached when the candidate is not newer, so adopting its
    # timestamp would date the record by its stalest contributor. That is not
    # cosmetic: updated_at drives the freshness check, so a regressed stamp
    # makes a just-resolved status read as expired and re-probes every call.
    merged["updated_at"] = _later_status_timestamp(current.get("updated_at"), candidate.get("updated_at"))
    return merged

def _compute_available_pct(status):
    if not status:
        return None
    values = [
        _normalize_pct_value(status.get("remaining_5h_pct")),
        _normalize_pct_value(status.get("remaining_week_pct")),
    ]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return min(values)

def _is_low_confidence_status_source(status):
    if not status:
        return False
    if status.get("structured"):
        # Exact rate_limits API data: trustworthy even when it comes from a
        # sessions/rollout path, which otherwise flags scraped-text noise.
        return False
    source_ref = str(status.get("source_ref") or "").replace(os.sep, "/")
    return "/sessions/" in source_ref and "/rollout" in source_ref

def _read_expected_account_email(auth_home):
    auth_path = os.path.join(auth_home, "auth.json")
    try:
        with open(auth_path, encoding="utf-8") as handle:
            auth = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    tokens = auth.get("tokens") or {}
    for token_name in ("id_token", "access_token"):
        claims = _decode_jwt_claims(tokens.get(token_name))
        email = claims.get("email")
        if not email and token_name == "access_token":
            profile = claims.get("https://api.openai.com/profile") or {}
            email = profile.get("email")
        if email:
            return str(email).strip().lower()
    return None

def _status_cache_hit(s, force_refresh=False, cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS, cache_only=False):
    return (
        cache_only
        or s.get("enabled", True) is False
        or (
            s.get("lastStatus")
            and not force_refresh
            and _is_status_cache_fresh(s, ttl_seconds=cache_ttl_seconds)
        )
    )

def record_status(store, name, payload):
    normalized = _normalize_status_payload(payload)
    updated = store["update_session"](name, lambda s: {
        **s,
        "lastStatus": normalized,
        "lastStatusAt": normalized["updated_at"],
    })
    if not updated:
        raise CdxError(f"Unknown session: {name}")
    return updated

def _fetch_codex_status(codex_status_fetcher, custom_codex_status_fetcher, default_status_timeout_seconds, session, timeout_seconds=None):
    if custom_codex_status_fetcher:
        return custom_codex_status_fetcher(session)
    timeout = timeout_seconds or default_status_timeout_seconds
    return codex_status_fetcher(session, timeout=timeout)

def _status_row_from_session(store, s):
    status = s.get("lastStatus")
    enabled = s.get("enabled", True) is not False
    row_status = status if enabled else None
    runtime = _session_runtime(store, s["name"])
    return {
        "session_name": s["name"],
        "label": s.get("label"),
        "provider": s["provider"],
        "enabled": enabled,
        # Carried so the ranking can honor the user's `--priority` and the
        # configured effort wherever it runs. Without these on the row, the
        # recommendation path could not see either, which is why `cdx next`
        # ignored `--priority` entirely.
        "priority": _row_priority(s),
        "reasoning_effort": _row_reasoning_effort(s),
        "active": bool(runtime) if enabled else False,
        "cwd": runtime.get("cwd") if runtime else None,
        "status": "enabled" if enabled else "disabled",
        "auth_status": (s.get("auth") or {}).get("status") or "unknown",
        "auth_checked_at": _to_local_iso((s.get("auth") or {}).get("lastCheckedAt")),
        "remaining_5h_pct": _normalize_pct_value(row_status.get("remaining_5h_pct")) if row_status else None,
        "remaining_week_pct": _normalize_pct_value(row_status.get("remaining_week_pct")) if row_status else None,
        "credits": row_status.get("credits") if row_status else None,
        "reset_credits_available": row_status.get("reset_credits_available") if row_status else None,
        "reset_credits": row_status.get("reset_credits") if row_status else None,
        "available_pct": _compute_available_pct(row_status),
        "reset_5h_at": row_status.get("reset_5h_at") if row_status else None,
        "reset_week_at": row_status.get("reset_week_at") if row_status else None,
        "reset_at": row_status.get("reset_at") if row_status else None,
        "updated_at": _to_local_iso(s.get("lastStatusAt")),
        "last_launched_at": _to_local_iso(s.get("lastLaunchedAt")),
    }

def format_list_rows(store):
    sessions = list_sessions(store)
    providers = {s["provider"] for s in sessions}
    has_multiple = len(providers) > 1
    sessions = sorted(
        sessions,
        key=lambda s: (
            1 if s.get("enabled", True) is False else 0,
            s.get("name", ""),
        ),
    )
    return [{
        "name": s["name"],
        "label": s.get("label"),
        "provider": s["provider"] if has_multiple else None,
        "enabled": s.get("enabled", True) is not False,
        "active": bool(_session_runtime(store, s["name"])) if s.get("enabled", True) is not False else False,
        "cwd": (_session_runtime(store, s["name"]) or {}).get("cwd"),
        "enabled_status": "disabled" if s.get("enabled", True) is False else "enabled",
        "status": s.get("lastStatus"),
        "launch": s.get("launch") or {},
        "updated_at": _to_local_iso(s.get("updatedAt")),
    } for s in sessions]

def _resolve_session_status(store, base_dir, env, fetch_codex_status, session,
    force_refresh=False,
    cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS,
    cache_only=False,
    status_timeout_seconds=None,):
    current_status = session.get("lastStatus")
    if session.get("enabled", True) is False:
        return current_status
    if cache_only:
        return current_status
    if current_status and not force_refresh and _is_status_cache_fresh(session, ttl_seconds=cache_ttl_seconds):
        return current_status
    source_root = session.get("authHome") or _get_session_auth_home(base_dir,
        session["name"], session["provider"]
    )
    if session["provider"] == PROVIDER_CODEX and fetch_codex_status:
        live_status = fetch_codex_status(
            {**session, "authHome": source_root},
            timeout_seconds=status_timeout_seconds,
        )
        if live_status:
            record_status(store, session["name"], live_status)
            return live_status

    expected_account_email = (
        _read_expected_account_email(source_root)
        if session["provider"] == PROVIDER_CODEX
        else None
    )
    artifact = find_latest_status_artifact(
        source_root,
        session["provider"],
        expected_account_email=expected_account_email,
    )
    if (
        session["provider"] == PROVIDER_CODEX
        and not artifact
        and os.path.abspath(base_dir) == os.path.abspath(get_cdx_home(env))
    ):
        global_root = _get_global_codex_home(env)
        if global_root and os.path.abspath(global_root) != os.path.abspath(source_root):
            artifact = find_latest_status_artifact(
                global_root,
                session["provider"],
                expected_account_email=expected_account_email,
                # The shared codex home can hold other accounts' rollouts;
                # structured payloads there cannot be attributed to ours.
                trust_unattributed_structured=False,
            )
    if not artifact:
        if _is_low_confidence_status_source(current_status):
            return None
        return current_status
    resolved = _normalize_status_payload({
        "usage_pct": artifact.get("usage_pct"),
        "remaining_5h_pct": artifact.get("remaining_5h_pct"),
        "remaining_week_pct": artifact.get("remaining_week_pct"),
        "credits": artifact.get("credits"),
        "reset_5h_at": artifact.get("reset_5h_at"),
        "reset_week_at": artifact.get("reset_week_at"),
        "reset_at": artifact.get("reset_at"),
        "updated_at": artifact.get("updated_at"),
        "raw_status_text": artifact.get("raw_status_text"),
        "source_ref": artifact.get("source_ref"),
        "structured": artifact.get("structured"),
    })
    if _is_low_confidence_status_source(current_status) and not _is_low_confidence_status_source(resolved):
        record_status(store, session["name"], resolved)
        return resolved
    if _is_status_newer(resolved, current_status):
        record_status(store, session["name"], resolved)
        return resolved
    if _status_has_more_detail(resolved, current_status):
        merged = _merge_status_payload(current_status, resolved)
        record_status(store, session["name"], merged)
        return merged
    return current_status or resolved

def _resolve_row_session(store, base_dir, env, fetch_codex_status, s,
    force_refresh=False,
    cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS,
    cache_only=False,
    status_timeout_seconds=None,):
    status = _resolve_session_status(store, base_dir, env, fetch_codex_status,
        s,
        force_refresh=force_refresh,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_only=cache_only,
        status_timeout_seconds=status_timeout_seconds,
    )
    return {
        **s,
        "lastStatus": status,
        "lastStatusAt": (status and status.get("updated_at")) or s.get("lastStatusAt"),
    }

def get_status_row(store, base_dir, env, fetch_codex_status, name,
    progress_callback=None,
    force_refresh=False,
    cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS,
    cache_only=False,
    status_timeout_seconds=None,):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    cache_hit = _status_cache_hit(
        session,
        force_refresh=force_refresh,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_only=cache_only,
    )
    if progress_callback:
        progress_callback({
            "event": "status_started",
            "session_count": 1,
            "check_count": 0 if cache_hit else 1,
        })
        if not cache_hit:
            progress_callback({
                "event": "session_started",
                "session_name": session["name"],
                "provider": session["provider"],
            })
    resolved = _resolve_row_session(store, base_dir, env, fetch_codex_status,
        session,
        force_refresh=force_refresh,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_only=cache_only,
        status_timeout_seconds=status_timeout_seconds,
    )
    if progress_callback:
        progress_callback({
            "event": "session_finished",
            "session_name": session["name"],
            "has_status": bool(resolved.get("lastStatus")),
            "cache_hit": cache_hit,
        })
        progress_callback({
            "event": "status_finished",
            "row_count": 1,
        })
    return _status_row_from_session(store, resolved)

def get_status_rows(store, base_dir, env, fetch_codex_status, progress_callback=None,
    force_refresh=False,
    cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS,
    cache_only=False,
    status_timeout_seconds=None,):
    sessions = list_sessions(store)

    cache_hits = {
        s["name"]: _status_cache_hit(
            s,
            force_refresh=force_refresh,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_only=cache_only,
        )
        for s in sessions
    }
    if progress_callback:
        progress_callback({
            "event": "status_started",
            "session_count": len(sessions),
            "check_count": sum(1 for cache_hit in cache_hits.values() if not cache_hit),
        })

    resolved_by_name = {}
    if sessions:
        max_workers = min(MAX_STATUS_WORKERS, len(sessions))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for s in sessions:
                cache_hit = cache_hits[s["name"]]
                if progress_callback and not cache_hit:
                    progress_callback({
                        "event": "session_started",
                        "session_name": s["name"],
                        "provider": s["provider"],
                    })
                futures[executor.submit(
                    _resolve_row_session,
                    store,
                    base_dir,
                    env,
                    fetch_codex_status,
                    s,
                    force_refresh=force_refresh,
                    cache_ttl_seconds=cache_ttl_seconds,
                    cache_only=cache_only,
                    status_timeout_seconds=status_timeout_seconds,
                )] = s
            for future in as_completed(futures):
                s = futures[future]
                try:
                    resolved = future.result()
                except CdxError as error:
                    if not str(error).startswith("Unknown session:"):
                        raise
                    continue
                resolved_by_name[s["name"]] = resolved
                if progress_callback:
                    progress_callback({
                        "event": "session_finished",
                        "session_name": s["name"],
                        "has_status": bool(resolved.get("lastStatus")),
                        "cache_hit": cache_hits[s["name"]],
                    })
    resolved = [resolved_by_name[s["name"]] for s in sessions if s["name"] in resolved_by_name]

    def sort_key(s):
        at = s.get("lastStatusAt") or ""
        disabled_rank = 1 if s.get("enabled", True) is False else 0
        return (disabled_rank, "" if at else "\xff", at, s["name"])

    resolved.sort(key=sort_key)
    enabled = [s for s in resolved if s.get("enabled", True) is not False]
    disabled = [s for s in resolved if s.get("enabled", True) is False]
    enabled.reverse()
    disabled.sort(key=lambda s: s["name"])
    resolved = enabled + disabled

    rows = []
    for s in resolved:
        rows.append(_status_row_from_session(store, s))
    if progress_callback:
        progress_callback({
            "event": "status_finished",
            "row_count": len(rows),
        })
    return rows
