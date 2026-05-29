import os
import shutil
import json
import base64
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from .backup_bundle import decode_bundle, encode_bundle
from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDERS, get_cdx_home
from .codex_usage import fetch_codex_rate_limits
from .errors import CdxError
from .session_store import create_session_store
from .status_source import find_latest_status_artifact

DEFAULT_PROVIDER = PROVIDER_CODEX
ALLOWED_PROVIDERS = set(PROVIDERS)
MAX_SESSION_NAME_LENGTH = 64
RESERVED_SESSION_NAMES = {
    "add",
    "clean",
    "context",
    "cp",
    "disable",
    "doctor",
    "enable",
    "export",
    "help",
    "handoff",
    "history",
    "import",
    "login",
    "logout",
    "mv",
    "notify",
    "ready",
    "repair",
    "ren",
    "rename",
    "rmv",
    "run",
    "select",
    "config",
    "set",
    "status",
    "unset",
    "update",
    "version",
    "--help",
    "-h",
    "--version",
    "-v",
}
STATUS_CACHE_TTL_SECONDS = 60
CLAUDE_STATUS_CACHE_TTL_SECONDS = 10 * 60
LAUNCH_POWER_VALUES = {"low", "medium", "high", "xhigh", "max"}
LAUNCH_REASONING_EFFORT_VALUES = {"low", "medium", "high"}
LAUNCH_PERMISSION_VALUES = {"review", "default", "auto", "full"}
MAX_LAUNCH_MODEL_LENGTH = 128
MIN_LAUNCH_PRIORITY = 0
MAX_LAUNCH_PRIORITY = 100


def _encode(name):
    return quote(name, safe="")


def _ensure_private_dir(path):
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        return
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def _get_global_codex_home(env=None):
    env = env or os.environ
    return env.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")


def _seed_codex_auth_from_global(auth_home, env=None):
    source_home = _get_global_codex_home(env)
    source_auth = os.path.join(source_home, "auth.json")
    dest_auth = os.path.join(auth_home, "auth.json")
    if source_home == auth_home or os.path.exists(dest_auth) or not os.path.isfile(source_auth):
        return False
    shutil.copy2(source_auth, dest_auth)
    return True


def _normalize_launch_settings(settings):
    normalized = {}
    if not settings:
        return normalized
    if "power" in settings and settings["power"] is not None:
        power = str(settings["power"]).strip().lower()
        if power not in LAUNCH_POWER_VALUES:
            raise CdxError(f"Unsupported power: {settings['power']}")
        normalized["power"] = power
    if "reasoning_effort" in settings and settings["reasoning_effort"] is not None:
        effort = str(settings["reasoning_effort"]).strip().lower()
        if effort not in LAUNCH_REASONING_EFFORT_VALUES:
            raise CdxError(f"Unsupported reasoning effort: {settings['reasoning_effort']}")
        normalized["reasoning_effort"] = effort
    if "permission" in settings and settings["permission"] is not None:
        permission = str(settings["permission"]).strip().lower()
        if permission not in LAUNCH_PERMISSION_VALUES:
            raise CdxError(f"Unsupported permission: {settings['permission']}")
        normalized["permission"] = permission
    if "fast" in settings and settings["fast"] is not None:
        value = settings["fast"]
        if isinstance(value, bool):
            normalized["fast"] = value
        else:
            text = str(value).strip().lower()
            if text in ("on", "true", "1", "yes"):
                normalized["fast"] = True
            elif text in ("off", "false", "0", "no"):
                normalized["fast"] = False
            else:
                raise CdxError(f"Unsupported fast value: {settings['fast']}")
    if "model" in settings and settings["model"] is not None:
        model = str(settings["model"]).strip()
        if not model:
            raise CdxError("Model cannot be empty.")
        if len(model) > MAX_LAUNCH_MODEL_LENGTH or any(ord(ch) < 32 or ord(ch) == 127 for ch in model):
            raise CdxError("Model contains unsupported characters.")
        normalized["model"] = model
    if "priority" in settings and settings["priority"] is not None:
        try:
            priority = int(settings["priority"])
        except (TypeError, ValueError) as error:
            raise CdxError(f"Unsupported priority: {settings['priority']}") from error
        if priority < MIN_LAUNCH_PRIORITY or priority > MAX_LAUNCH_PRIORITY:
            raise CdxError(f"Unsupported priority: {settings['priority']}")
        normalized["priority"] = priority
    return normalized


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


def _process_is_running(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _safe_relpath(path):
    normalized = os.path.normpath(str(path or "").replace("\\", "/")).replace("\\", "/")
    if (
        not normalized
        or normalized == "."
        or normalized.startswith("/")
        or (len(normalized) > 1 and normalized[1] == ":")
        or normalized == ".."
        or normalized.startswith("../")
    ):
        raise CdxError("Bundle contains an unsafe file path.")
    return normalized


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


def _status_cache_ttl_seconds(session, ttl_seconds=STATUS_CACHE_TTL_SECONDS):
    if session.get("provider") == PROVIDER_CLAUDE and ttl_seconds == STATUS_CACHE_TTL_SECONDS:
        return CLAUDE_STATUS_CACHE_TTL_SECONDS
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


def _ensure_claude_attribution_disabled(auth_home):
    settings_dir = os.path.join(auth_home, ".claude")
    settings_path = os.path.join(settings_dir, "settings.json")
    try:
        os.makedirs(settings_dir, exist_ok=True)
        with open(settings_path, "r", encoding="utf-8") as handle:
            settings = json.load(handle)
    except FileNotFoundError:
        settings = {}
    except (OSError, json.JSONDecodeError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    settings["includeCoAuthoredBy"] = False
    try:
        with open(settings_path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError:
        return False
    return True


def create_session_service(options=None):
    if options is None:
        options = {}
    env = options.get("env", os.environ)
    base_dir = options.get("base_dir") or get_cdx_home(env)
    store = options.get("store") or create_session_store(base_dir)
    codex_status_fetcher = options.get("fetchCodexRateLimits") or fetch_codex_rate_limits

    def _get_session_root(name):
        return os.path.join(base_dir, "profiles", _encode(name))

    def _get_session_auth_home(name, provider):
        root = _get_session_root(name)
        if provider == PROVIDER_CLAUDE:
            return os.path.join(root, "claude-home")
        if provider == PROVIDER_ANTIGRAVITY:
            return os.path.join(root, "antigravity-home")
        return root

    def _normalize_provider(provider):
        value = provider or DEFAULT_PROVIDER
        if value not in ALLOWED_PROVIDERS:
            raise CdxError(f"Unsupported provider: {value}")
        return value

    def _runtime_is_active(runtime):
        return (
            isinstance(runtime, dict)
            and runtime.get("status") == "running"
            and _process_is_running(runtime.get("pid"))
        )

    def _session_runtime(name):
        state = store["read_session_state"](name)
        if not state:
            return None
        runtime = state.get("runtime")
        if _runtime_is_active(runtime):
            return runtime
        if isinstance(runtime, dict) and runtime.get("status") == "running":
            store["write_session_state"](name, {
                **state,
                "status": "ready",
                "runtime": {
                    **runtime,
                    "status": "stale",
                    "endedAt": _local_now_iso(),
                },
            })
        return None

    def _validate_new_session_name(name):
        if not name:
            raise CdxError("Session name is required")
        if str(name) != str(name).strip():
            raise CdxError("Session name cannot start or end with whitespace")
        if len(str(name)) > MAX_SESSION_NAME_LENGTH:
            raise CdxError(f"Session name is too long (max {MAX_SESSION_NAME_LENGTH} characters)")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in str(name)):
            raise CdxError("Session name cannot contain control characters")
        if name in RESERVED_SESSION_NAMES:
            raise CdxError(f"Session name is reserved: {name}")

    def _build_export_session_record(session):
        return {
            "name": session["name"],
            "provider": session["provider"],
            "enabled": session.get("enabled", True) is not False,
            "createdAt": session.get("createdAt"),
            "updatedAt": session.get("updatedAt"),
            "lastLaunchedAt": session.get("lastLaunchedAt"),
            "lastStatusAt": session.get("lastStatusAt"),
            "lastStatus": session.get("lastStatus"),
            "launch": session.get("launch"),
            "auth": session.get("auth"),
        }

    def _auth_bundle_paths(provider):
        if provider == PROVIDER_CLAUDE:
            return [
                "claude-home/configs/default.json",
                "claude-home/credentials/default.json",
                "claude-home/.claude/.credentials.json",
                "claude-home/.claude.json",
                "claude-home/auth.json",
            ]
        return [
            "auth.json",
        ]

    def _collect_auth_files(session_root, provider, session_name=None, progress_callback=None):
        files = []
        total_bytes = 0
        if not os.path.isdir(session_root):
            return {"files": files, "file_count": 0, "bytes": 0}
        for rel_path in _auth_bundle_paths(provider):
            full_path = os.path.join(session_root, rel_path)
            if not os.path.isfile(full_path):
                continue
            with open(full_path, "rb") as handle:
                raw_content = handle.read()
                total_bytes += len(raw_content)
                content = base64.b64encode(raw_content).decode("ascii")
            files.append({"path": rel_path.replace(os.sep, "/"), "data_b64": content})
            if progress_callback:
                progress_callback({
                    "event": "profile_progress",
                    "session_name": session_name,
                    "file_count": len(files),
                    "bytes": total_bytes,
                })
        return {"files": files, "file_count": len(files), "bytes": total_bytes}

    def _resolve_session_subset(session_names):
        if not session_names:
            return list_sessions()
        by_name = {session["name"]: session for session in list_sessions()}
        selected = []
        for name in session_names:
            session = by_name.get(name)
            if not session:
                raise CdxError(f"Unknown session: {name}")
            selected.append(session)
        return selected

    def create_session(name, provider=DEFAULT_PROVIDER):
        _validate_new_session_name(name)
        normalized_provider = _normalize_provider(provider)
        session_root = _get_session_root(name)
        auth_home = _get_session_auth_home(name, normalized_provider)
        _ensure_private_dir(base_dir)
        _ensure_private_dir(os.path.join(base_dir, "profiles"))
        _ensure_private_dir(session_root)
        _ensure_private_dir(auth_home)
        if normalized_provider == PROVIDER_CODEX:
            _seed_codex_auth_from_global(auth_home, env=env)
        if normalized_provider == PROVIDER_CLAUDE:
            _ensure_claude_attribution_disabled(auth_home)
        now = _local_now_iso()
        session = {
            "name": name,
            "provider": normalized_provider,
            "enabled": True,
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
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        session_root = session.get("sessionRoot") or _get_session_root(name)
        quarantine_root = None
        if os.path.exists(session_root):
            profiles_dir = os.path.dirname(session_root)
            os.makedirs(profiles_dir, exist_ok=True)
            quarantine_root = tempfile.mkdtemp(prefix=f".{_encode(name)}.remove.", dir=profiles_dir)
            os.rmdir(quarantine_root)
            os.rename(session_root, quarantine_root)
        try:
            removed = store["remove_session"](name)
        except Exception:
            if quarantine_root and os.path.exists(quarantine_root) and not os.path.exists(session_root):
                os.rename(quarantine_root, session_root)
            raise
        if not removed:
            if quarantine_root and os.path.exists(quarantine_root) and not os.path.exists(session_root):
                os.rename(quarantine_root, session_root)
            raise CdxError(f"Unknown session: {name}")
        if quarantine_root:
            try:
                shutil.rmtree(quarantine_root)
            except OSError as error:
                raise CdxError(
                    f"Removed session {name}, but failed to delete archived profile {quarantine_root}: {error}"
                ) from error
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
        source_root = source.get("sessionRoot") or _get_session_root(source_name)
        dest_root = _get_session_root(dest_name)
        if not existing and os.path.exists(dest_root):
            raise CdxError(f"Session profile already exists: {dest_name}")
        dest_auth_home = _get_session_auth_home(dest_name, source["provider"])
        profiles_dir = os.path.dirname(dest_root)
        os.makedirs(profiles_dir, exist_ok=True)
        temp_parent = tempfile.mkdtemp(prefix=f".{_encode(dest_name)}.copy.", dir=profiles_dir)
        temp_root = os.path.join(temp_parent, "profile")
        backup_root = None
        moved_temp = False
        now = _local_now_iso()
        replacement = {
            "name": dest_name,
            "provider": source["provider"],
            "enabled": True,
            "sessionRoot": dest_root,
            "authHome": dest_auth_home,
            "createdAt": now,
            "updatedAt": now,
            "lastLaunchedAt": None,
            "lastStatusAt": None,
            "lastStatus": None,
            **({"launch": source.get("launch")} if source.get("launch") else {}),
            "auth": {
                "status": "unknown",
                "lastCheckedAt": None,
                "lastAuthenticatedAt": None,
                "lastLoggedOutAt": None,
            },
        }
        try:
            shutil.copytree(source_root, temp_root)
            if existing:
                backup_root = tempfile.mkdtemp(prefix=f".{_encode(dest_name)}.backup.", dir=profiles_dir)
                os.rmdir(backup_root)
                if os.path.exists(dest_root):
                    os.rename(dest_root, backup_root)
            os.rename(temp_root, dest_root)
            moved_temp = True
            result = store["replace_session"](dest_name, replacement)
            overwritten = bool(existing)
        except Exception:
            if moved_temp and os.path.exists(dest_root):
                shutil.rmtree(dest_root, ignore_errors=True)
            if backup_root and os.path.exists(backup_root) and not os.path.exists(dest_root):
                os.rename(backup_root, dest_root)
            raise
        finally:
            if backup_root and os.path.exists(backup_root):
                shutil.rmtree(backup_root, ignore_errors=True)
            shutil.rmtree(temp_parent, ignore_errors=True)
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
        if session.get("enabled", True) is False:
            raise CdxError(f"Session is disabled: {name}")
        state = store["read_session_state"](name)
        if not state:
            raise CdxError(f"Session state missing for {name}. Reconnect required.")
        now = _local_now_iso()
        store["write_session_state"](name, {**state, "rehydratedAt": now})
        return store["update_session"](name, lambda s: {
            **s, "updatedAt": now, "lastLaunchedAt": now
        })

    def start_session_runtime(name, payload=None):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        state = store["read_session_state"](name)
        if not state:
            raise CdxError(f"Session state missing for {name}. Reconnect required.")
        payload = dict(payload or {})
        now = _local_now_iso()
        runtime = {
            "status": "running",
            "runId": payload.get("runId") or uuid.uuid4().hex,
            "startedAt": payload.get("startedAt") or now,
            "pid": payload.get("pid") or os.getpid(),
            "command": payload.get("command"),
            "label": payload.get("label"),
            "transcriptPath": payload.get("transcript_path") or payload.get("transcriptPath"),
        }
        store["write_session_state"](name, {
            **state,
            "status": "running",
            "runtime": runtime,
        })
        return runtime

    def finish_session_runtime(name, run_id=None, payload=None):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        state = store["read_session_state"](name)
        if not state:
            return None
        runtime = state.get("runtime") or {}
        if run_id and runtime.get("runId") != run_id:
            return runtime
        payload = dict(payload or {})
        updated_runtime = {
            **runtime,
            "status": payload.get("status") or "stopped",
            "endedAt": payload.get("endedAt") or _local_now_iso(),
        }
        if "returncode" in payload:
            updated_runtime["returncode"] = payload["returncode"]
        store["write_session_state"](name, {
            **state,
            "status": "ready",
            "runtime": updated_runtime,
        })
        return updated_runtime

    def ensure_session_state(name):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        state = store["read_session_state"](name)
        if state:
            return state
        repaired = {
            "provider": session["provider"],
            "status": "ready",
            "rehydratedAt": None,
        }
        store["write_session_state"](name, repaired)
        return repaired

    def list_sessions():
        return store["list_sessions"]()

    def get_session(name):
        return store["get_session"](name)

    def set_session_enabled(name, enabled):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        now = _local_now_iso()
        return store["update_session"](name, lambda s: {
            **s,
            "enabled": bool(enabled),
            "updatedAt": now,
        })

    def set_launch_settings(name, settings):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        updates = _normalize_launch_settings(settings)
        if not updates:
            raise CdxError("At least one launch setting is required.")
        current = _normalize_launch_settings(session.get("launch") or {})
        launch = {**current, **updates}
        now = _local_now_iso()
        return store["update_session"](name, lambda s: {
            **s,
            "launch": launch,
            "updatedAt": now,
        })

    def unset_launch_settings(name, keys):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        if not keys:
            raise CdxError("At least one launch setting is required.")
        allowed = {"power", "permission", "fast", "model"}
        unknown = [key for key in keys if key not in allowed]
        if unknown:
            raise CdxError(f"Unsupported launch setting: {', '.join(unknown)}")
        current = dict(session.get("launch") or {})
        for key in keys:
            current.pop(key, None)
        now = _local_now_iso()

        def updater(s):
            updated = {**s, "updatedAt": now}
            if current:
                updated["launch"] = current
            else:
                updated.pop("launch", None)
            return updated

        return store["update_session"](name, updater)

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

    def record_launch_history(name, payload):
        session = store["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        entry = {
            "schema_version": 1,
            "session_name": session["name"],
            "provider": session["provider"],
            "launch": session.get("launch") or {},
            **payload,
        }
        store["append_launch_history"](entry)
        return entry

    def get_launch_history(name=None, limit=20):
        if name and not store["get_session"](name):
            raise CdxError(f"Unknown session: {name}")
        return store["list_launch_history"](session_name=name, limit=limit)

    def _resolve_session_status(session, force_refresh=False, cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS):
        current_status = session.get("lastStatus")
        if session.get("enabled", True) is False:
            return current_status
        if current_status and not force_refresh and _is_status_cache_fresh(session, ttl_seconds=cache_ttl_seconds):
            return current_status
        source_root = session.get("authHome") or _get_session_auth_home(
            session["name"], session["provider"]
        )
        if session["provider"] == PROVIDER_CODEX and codex_status_fetcher:
            live_status = codex_status_fetcher({**session, "authHome": source_root})
            if live_status:
                record_status(session["name"], live_status)
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

    def get_status_rows(progress_callback=None, force_refresh=False, cache_ttl_seconds=STATUS_CACHE_TTL_SECONDS):
        sessions = list_sessions()
        if progress_callback:
            progress_callback({
                "event": "status_started",
                "session_count": len(sessions),
            })
        resolved = []
        for s in sessions:
            cache_hit = (
                s.get("enabled", True) is False
                or (
                    s.get("lastStatus")
                    and not force_refresh
                    and _is_status_cache_fresh(s, ttl_seconds=cache_ttl_seconds)
                )
            )
            if progress_callback and not cache_hit:
                progress_callback({
                    "event": "session_started",
                    "session_name": s["name"],
                    "provider": s["provider"],
                })
            status = _resolve_session_status(
                s,
                force_refresh=force_refresh,
                cache_ttl_seconds=cache_ttl_seconds,
            )
            if progress_callback:
                progress_callback({
                    "event": "session_finished",
                    "session_name": s["name"],
                    "has_status": bool(status),
                })
            resolved.append({
                **s,
                "lastStatus": status,
                "lastStatusAt": (status and status.get("updated_at")) or s.get("lastStatusAt"),
            })

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
            status = s.get("lastStatus")
            enabled = s.get("enabled", True) is not False
            row_status = status if enabled else None
            rows.append({
                "session_name": s["name"],
                "provider": s["provider"],
                "enabled": enabled,
                "active": bool(_session_runtime(s["name"])) if enabled else False,
                "status": "enabled" if enabled else "disabled",
                "auth_status": (s.get("auth") or {}).get("status") or "unknown",
                "auth_checked_at": _to_local_iso((s.get("auth") or {}).get("lastCheckedAt")),
                "remaining_5h_pct": row_status.get("remaining_5h_pct") if row_status else None,
                "remaining_week_pct": row_status.get("remaining_week_pct") if row_status else None,
                "credits": row_status.get("credits") if row_status else None,
                "available_pct": _compute_available_pct(row_status),
                "reset_5h_at": row_status.get("reset_5h_at") if row_status else None,
                "reset_week_at": row_status.get("reset_week_at") if row_status else None,
                "reset_at": row_status.get("reset_at") if row_status else None,
                "updated_at": _to_local_iso(s.get("lastStatusAt")),
                "last_launched_at": _to_local_iso(s.get("lastLaunchedAt")),
            })
        if progress_callback:
            progress_callback({
                "event": "status_finished",
                "row_count": len(rows),
            })
        return rows

    def format_list_rows():
        sessions = list_sessions()
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
            "provider": s["provider"] if has_multiple else None,
            "enabled": s.get("enabled", True) is not False,
            "active": bool(_session_runtime(s["name"])) if s.get("enabled", True) is not False else False,
            "enabled_status": "disabled" if s.get("enabled", True) is False else "enabled",
            "status": s.get("lastStatus"),
            "launch": s.get("launch") or {},
            "updated_at": _to_local_iso(s.get("updatedAt")),
        } for s in sessions]

    def get_session_auth_home(name, provider):
        return _get_session_auth_home(name, provider)

    def get_session_root(name):
        return _get_session_root(name)

    def export_bundle(file_path, include_auth=False, session_names=None, passphrase=None, force=False, progress_callback=None):
        if not file_path:
            raise CdxError("Export path is required.")
        if os.path.exists(file_path) and not force:
            raise CdxError(f"Export path already exists: {file_path}")

        sessions = _resolve_session_subset(session_names)
        payload = {
            "schema_version": 1,
            "created_at": _local_now_iso(),
            "include_auth": bool(include_auth),
            "sessions": [],
            "states": {},
            "profiles": {},
        }
        profile_file_count = 0
        profile_bytes = 0
        if progress_callback:
            progress_callback({
                "event": "export_started",
                "include_auth": bool(include_auth),
                "session_count": len(sessions),
                "session_names": [session["name"] for session in sessions],
            })
        for session in sessions:
            if progress_callback:
                progress_callback({"event": "session_started", "session_name": session["name"]})
            payload["sessions"].append(_build_export_session_record(session))
            state = store["read_session_state"](session["name"])
            if state is not None:
                payload["states"][session["name"]] = state
            if include_auth:
                session_root = session.get("sessionRoot") or _get_session_root(session["name"])
                profile = _collect_auth_files(session_root, session["provider"], session["name"], progress_callback)
                payload["profiles"][session["name"]] = profile["files"]
                profile_file_count += profile["file_count"]
                profile_bytes += profile["bytes"]
            if progress_callback:
                progress_callback({"event": "session_finished", "session_name": session["name"]})

        if progress_callback:
            progress_callback({"event": "encoding_started"})
        bundle_bytes = encode_bundle(payload, include_auth=include_auth, passphrase=passphrase)
        if progress_callback:
            progress_callback({"event": "writing_started", "path": file_path, "bundle_size_bytes": len(bundle_bytes)})
        _ensure_private_dir(os.path.dirname(os.path.abspath(file_path)) or ".")
        with open(file_path, "wb") as handle:
            handle.write(bundle_bytes)
        if sys.platform != "win32":
            try:
                os.chmod(file_path, 0o600)
            except OSError:
                pass
        return {
            "path": file_path,
            "include_auth": include_auth,
            "session_names": [session["name"] for session in sessions],
            "session_count": len(sessions),
            "profile_file_count": profile_file_count if include_auth else None,
            "profile_bytes": profile_bytes if include_auth else None,
            "bundle_size_bytes": len(bundle_bytes),
        }

    def import_bundle(file_path, passphrase=None, session_names=None, force=False):
        if not file_path or not os.path.isfile(file_path):
            raise CdxError(f"Bundle file not found: {file_path}")
        with open(file_path, "rb") as handle:
            decoded = decode_bundle(handle.read(), passphrase=passphrase)
        payload = decoded["payload"]
        imported_sessions = payload.get("sessions") or []
        if payload.get("schema_version") != 1:
            raise CdxError("Unsupported bundle payload schema version.")

        selected_names = set(session_names or [])
        if selected_names:
            imported_sessions = [item for item in imported_sessions if item["name"] in selected_names]
            missing_names = sorted(selected_names - {item["name"] for item in imported_sessions})
            if missing_names:
                raise CdxError(f"Bundle does not contain requested sessions: {', '.join(missing_names)}")
        names = [item["name"] for item in imported_sessions]

        existing = {session["name"] for session in list_sessions()}
        conflicts = [name for name in names if name in existing]
        if conflicts and not force:
            raise CdxError(f"Import would overwrite existing sessions: {', '.join(conflicts)}")

        for session_payload in imported_sessions:
            name = session_payload["name"]
            _validate_new_session_name(name)
            provider = _normalize_provider(session_payload["provider"])
            if name in existing:
                remove_session(name)

            session_root = _get_session_root(name)
            auth_home = _get_session_auth_home(name, provider)
            _ensure_private_dir(base_dir)
            _ensure_private_dir(os.path.join(base_dir, "profiles"))
            _ensure_private_dir(session_root)
            _ensure_private_dir(auth_home)

            session_record = {
                **session_payload,
                "provider": provider,
                "enabled": session_payload.get("enabled", True) is not False,
                "sessionRoot": session_root,
                "authHome": auth_home,
            }
            store["replace_session"](name, session_record)

            state = (payload.get("states") or {}).get(name)
            if state is not None:
                store["write_session_state"](name, state)

            for item in (payload.get("profiles") or {}).get(name, []):
                rel_path = _safe_relpath(item.get("path"))
                try:
                    content = base64.b64decode(item.get("data_b64", "").encode("ascii"))
                except (AttributeError, ValueError, UnicodeEncodeError) as error:
                    raise CdxError(f"Bundle contains invalid file data for session {name}: {rel_path}") from error
                dest_path = os.path.join(session_root, rel_path)
                _ensure_private_dir(os.path.dirname(dest_path))
                with open(dest_path, "wb") as handle:
                    handle.write(content)
                if sys.platform != "win32":
                    try:
                        os.chmod(dest_path, 0o600)
                    except OSError:
                        pass

        return {
            "path": file_path,
            "session_names": names,
            "include_auth": bool(decoded["meta"].get("include_auth")),
        }

    return {
        "create_session": create_session,
        "remove_session": remove_session,
        "copy_session": copy_session,
        "rename_session": rename_session,
        "launch_session": launch_session,
        "start_session_runtime": start_session_runtime,
        "finish_session_runtime": finish_session_runtime,
        "ensure_session_state": ensure_session_state,
        "list_sessions": list_sessions,
        "get_session": get_session,
        "set_session_enabled": set_session_enabled,
        "set_launch_settings": set_launch_settings,
        "unset_launch_settings": unset_launch_settings,
        "record_status": record_status,
        "record_launch_history": record_launch_history,
        "get_launch_history": get_launch_history,
        "update_auth_state": update_auth_state,
        "get_status_rows": get_status_rows,
        "format_list_rows": format_list_rows,
        "get_session_auth_home": get_session_auth_home,
        "get_session_root": get_session_root,
        "export_bundle": export_bundle,
        "import_bundle": import_bundle,
        "base_dir": base_dir,
        "normalize_provider": _normalize_provider,
    }
