import os
import shutil
import json
import base64
from datetime import datetime, timezone
from urllib.parse import quote

from .config import get_cdx_home
from .errors import CdxError
from .session_store import create_session_store
from .status_source import find_latest_status_artifact

DEFAULT_PROVIDER = "codex"
ALLOWED_PROVIDERS = {"codex", "claude"}
RESERVED_SESSION_NAMES = {
    "add",
    "clean",
    "cp",
    "help",
    "login",
    "logout",
    "mv",
    "ren",
    "rename",
    "rmv",
    "status",
    "version",
    "--help",
    "-h",
    "--version",
    "-v",
}


def _encode(name):
    return quote(name, safe="")


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


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


def _normalize_status_payload(payload=None):
    if payload is None:
        payload = {}
    now = _local_now_iso()
    return {
        "usage_pct": payload.get("usage_pct"),
        "remaining_5h_pct": payload.get("remaining_5h_pct"),
        "remaining_week_pct": payload.get("remaining_week_pct"),
        "credits": payload.get("credits"),
        "reset_5h_at": payload.get("reset_5h_at"),
        "reset_week_at": payload.get("reset_week_at"),
        "reset_at": payload.get("reset_at") or payload.get("reset_week_at") or payload.get("reset_5h_at"),
        "updated_at": _to_local_iso(payload.get("updated_at") or payload.get("captured_at") or now),
        "raw_status_text": payload.get("raw_status_text"),
        "source_ref": payload.get("source_ref"),
    }


def _parse_status_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


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
        "reset_5h_at",
        "reset_week_at",
        "reset_at",
        "raw_status_text",
        "source_ref",
    ]
    return any(current.get(field) is None and candidate.get(field) is not None for field in fields)


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
        "reset_5h_at",
        "reset_week_at",
        "reset_at",
        "raw_status_text",
        "source_ref",
    ]:
        if merged.get(field) is None and candidate.get(field) is not None:
            merged[field] = candidate[field]

    merged["updated_at"] = candidate.get("updated_at") or current.get("updated_at")
    return merged


def _compute_available_pct(status):
    if not status:
        return None
    values = [
        status.get("remaining_5h_pct"),
        status.get("remaining_week_pct"),
    ]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return min(values)


def _is_low_confidence_status_source(status):
    if not status:
        return False
    source_ref = str(status.get("source_ref") or "").replace(os.sep, "/")
    return "/sessions/" in source_ref and "/rollout" in source_ref


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


def _read_expected_account_email(auth_home):
    auth_path = os.path.join(auth_home, "auth.json")
    try:
        with open(auth_path, "r", encoding="utf-8") as handle:
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


def create_session_service(options=None):
    if options is None:
        options = {}
    env = options.get("env", os.environ)
    base_dir = options.get("base_dir") or get_cdx_home(env)
    store = options.get("store") or create_session_store(base_dir)

    def _get_session_root(name):
        return os.path.join(base_dir, "profiles", _encode(name))

    def _get_session_auth_home(name, provider):
        root = _get_session_root(name)
        if provider == "claude":
            return os.path.join(root, "claude-home")
        return root

    def _normalize_provider(provider):
        value = provider or DEFAULT_PROVIDER
        if value not in ALLOWED_PROVIDERS:
            raise CdxError(f"Unsupported provider: {value}")
        return value

    def _validate_new_session_name(name):
        if not name:
            raise CdxError("Session name is required")
        if name in RESERVED_SESSION_NAMES:
            raise CdxError(f"Session name is reserved: {name}")

    def create_session(name, provider=DEFAULT_PROVIDER):
        _validate_new_session_name(name)
        normalized_provider = _normalize_provider(provider)
        session_root = _get_session_root(name)
        auth_home = _get_session_auth_home(name, normalized_provider)
        os.makedirs(auth_home, exist_ok=True)
        now = _local_now_iso()
        session = {
            "name": name,
            "provider": normalized_provider,
            "sessionRoot": session_root,
            "authHome": auth_home,
            "createdAt": now,
            "updatedAt": now,
            "lastLaunchedAt": None,
            "lastStatusAt": None,
            "lastStatus": None,
            "auth": {
                "status": "unknown",
                "lastCheckedAt": None,
                "lastAuthenticatedAt": None,
                "lastLoggedOutAt": None,
            },
        }
        result = store["add_session"](session)
        if not result["ok"]:
            raise CdxError(f"Session already exists: {name}")
        return result["session"]

    def remove_session(name):
        removed = store["remove_session"](name)
        if not removed:
            raise CdxError(f"Unknown session: {name}")
        session_root = removed.get("sessionRoot") or _get_session_root(name)
        shutil.rmtree(session_root, ignore_errors=True)
        return removed

    def copy_session(source_name, dest_name):
        if source_name == dest_name:
            raise CdxError("Source and destination session names must be different")
        _validate_new_session_name(dest_name)
        source = store["get_session"](source_name)
        if not source:
            raise CdxError(f"Unknown session: {source_name}")
        existing = store["get_session"](dest_name)
        overwritten = False
        if existing:
            dest_root = existing.get("sessionRoot") or _get_session_root(dest_name)
            store["remove_session"](dest_name)
            shutil.rmtree(dest_root, ignore_errors=True)
            overwritten = True
        source_root = source.get("sessionRoot") or _get_session_root(source_name)
        dest_root = _get_session_root(dest_name)
        dest_auth_home = _get_session_auth_home(dest_name, source["provider"])
        shutil.copytree(source_root, dest_root)
        now = _local_now_iso()
        result = store["add_session"]({
            "name": dest_name,
            "provider": source["provider"],
            "sessionRoot": dest_root,
            "authHome": dest_auth_home,
            "createdAt": now,
            "updatedAt": now,
            "lastLaunchedAt": None,
            "lastStatusAt": None,
            "lastStatus": None,
            "auth": {
                "status": "unknown",
                "lastCheckedAt": None,
                "lastAuthenticatedAt": None,
                "lastLoggedOutAt": None,
            },
        })
        if not result["ok"]:
            raise CdxError(f"Failed to create session: {dest_name}")
        return {"session": result["session"], "overwritten": overwritten}

    def rename_session(source_name, dest_name):
        if source_name == dest_name:
            raise CdxError("Source and destination session names must be different")
        _validate_new_session_name(dest_name)
        source = store["get_session"](source_name)
        if not source:
            raise CdxError(f"Unknown session: {source_name}")
        if store["get_session"](dest_name):
            raise CdxError(f"Session already exists: {dest_name}")

        source_root = source.get("sessionRoot") or _get_session_root(source_name)
        dest_root = _get_session_root(dest_name)
        if os.path.exists(dest_root):
            raise CdxError(f"Session profile already exists: {dest_name}")

        if os.path.exists(source_root):
            os.rename(source_root, dest_root)
            moved_profile = True
        else:
            moved_profile = False

        now = _local_now_iso()
        try:
            result = store["rename_session"](source_name, dest_name, lambda s: {
                **s,
                "name": dest_name,
                "sessionRoot": dest_root,
                "authHome": _get_session_auth_home(dest_name, s["provider"]),
                "updatedAt": now,
            })
        except Exception:
            if moved_profile and os.path.exists(dest_root) and not os.path.exists(source_root):
                os.rename(dest_root, source_root)
            raise

        if not result["ok"]:
            if moved_profile and os.path.exists(dest_root) and not os.path.exists(source_root):
                os.rename(dest_root, source_root)
            if result["reason"] == "exists":
                raise CdxError(f"Session already exists: {dest_name}")
            raise CdxError(f"Unknown session: {source_name}")
        return result["session"]

    def launch_session(name):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        state = store["read_session_state"](name)
        if not state:
            raise CdxError(f"Session state missing for {name}. Reconnect required.")
        now = _local_now_iso()
        store["write_session_state"](name, {**state, "rehydratedAt": now})
        return store["update_session"](name, lambda s: {
            **s, "updatedAt": now, "lastLaunchedAt": now
        })

    def list_sessions():
        return store["list_sessions"]()

    def get_session(name):
        return store["get_session"](name)

    def record_status(name, payload):
        normalized = _normalize_status_payload(payload)
        updated = store["update_session"](name, lambda s: {
            **s,
            "lastStatus": normalized,
            "lastStatusAt": normalized["updated_at"],
        })
        if not updated:
            raise CdxError(f"Unknown session: {name}")
        return updated

    def _resolve_session_status(session):
        current_status = session.get("lastStatus")
        source_root = session.get("authHome") or _get_session_auth_home(
            session["name"], session["provider"]
        )
        expected_account_email = (
            _read_expected_account_email(source_root)
            if session["provider"] == "codex"
            else None
        )
        artifact = find_latest_status_artifact(
            source_root,
            session["provider"],
            expected_account_email=expected_account_email,
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
        })
        if _is_low_confidence_status_source(current_status) and not _is_low_confidence_status_source(resolved):
            record_status(session["name"], resolved)
            return resolved
        if _is_status_newer(resolved, current_status):
            record_status(session["name"], resolved)
            return resolved
        if _status_has_more_detail(resolved, current_status):
            merged = _merge_status_payload(current_status, resolved)
            record_status(session["name"], merged)
            return merged
        return current_status or resolved

    def update_auth_state(name, updater):
        now = _local_now_iso()
        updated = store["update_session"](name, lambda s: {
            **s,
            "updatedAt": now,
            "auth": updater(s.get("auth") or {}),
        })
        if not updated:
            raise CdxError(f"Unknown session: {name}")
        return updated

    def get_status_rows():
        sessions = list_sessions()
        resolved = []
        for s in sessions:
            status = _resolve_session_status(s)
            resolved.append({
                **s,
                "lastStatus": status,
                "lastStatusAt": (status and status.get("updated_at")) or s.get("lastStatusAt"),
            })

        def sort_key(s):
            at = s.get("lastStatusAt") or ""
            return ("" if at else "\xff", at, s["name"])

        resolved.sort(key=sort_key)
        resolved.reverse()

        rows = []
        for s in resolved:
            status = s.get("lastStatus")
            rows.append({
                "session_name": s["name"],
                "provider": s["provider"],
                "auth_home": s.get("authHome") or _get_session_auth_home(s["name"], s["provider"]),
                "remaining_5h_pct": status.get("remaining_5h_pct") if status else None,
                "remaining_week_pct": status.get("remaining_week_pct") if status else None,
                "credits": status.get("credits") if status else None,
                "available_pct": _compute_available_pct(status),
                "reset_5h_at": status.get("reset_5h_at") if status else None,
                "reset_week_at": status.get("reset_week_at") if status else None,
                "reset_at": status.get("reset_at") if status else None,
                "updated_at": _to_local_iso(s.get("lastStatusAt")),
            })
        return rows

    def format_list_rows():
        sessions = list_sessions()
        providers = {s["provider"] for s in sessions}
        has_multiple = len(providers) > 1
        return [{
            "name": s["name"],
            "provider": s["provider"] if has_multiple else None,
            "status": s.get("lastStatus"),
            "updated_at": _to_local_iso(s.get("updatedAt")),
        } for s in sessions]

    def get_session_auth_home(name, provider):
        return _get_session_auth_home(name, provider)

    def get_session_root(name):
        return _get_session_root(name)

    return {
        "create_session": create_session,
        "remove_session": remove_session,
        "copy_session": copy_session,
        "rename_session": rename_session,
        "launch_session": launch_session,
        "list_sessions": list_sessions,
        "get_session": get_session,
        "record_status": record_status,
        "update_auth_state": update_auth_state,
        "get_status_rows": get_status_rows,
        "format_list_rows": format_list_rows,
        "get_session_auth_home": get_session_auth_home,
        "get_session_root": get_session_root,
        "normalize_provider": _normalize_provider,
    }
