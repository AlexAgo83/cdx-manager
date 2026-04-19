import os
import shutil
import json
import base64
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote

from .backup_bundle import decode_bundle, encode_bundle
from .config import get_cdx_home
from .errors import CdxError
from .session_store import create_session_store
from .status_source import find_latest_status_artifact

DEFAULT_PROVIDER = "codex"
ALLOWED_PROVIDERS = {"codex", "claude"}
MAX_SESSION_NAME_LENGTH = 64
RESERVED_SESSION_NAMES = {
    "add",
    "clean",
    "cp",
    "doctor",
    "export",
    "help",
    "import",
    "login",
    "logout",
    "mv",
    "notify",
    "repair",
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


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


def _safe_relpath(path):
    normalized = str(path or "").replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("../") or "/../" in f"/{normalized}/":
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
            "createdAt": session.get("createdAt"),
            "updatedAt": session.get("updatedAt"),
            "lastLaunchedAt": session.get("lastLaunchedAt"),
            "lastStatusAt": session.get("lastStatusAt"),
            "lastStatus": session.get("lastStatus"),
            "auth": session.get("auth"),
        }

    def _collect_profile_files(session_root):
        excluded_dirs = {"log", "tmp", "cache", "__pycache__", "shell_snapshots"}
        files = []
        if not os.path.isdir(session_root):
            return files
        for dirpath, dirnames, filenames in os.walk(session_root):
            dirnames[:] = [name for name in dirnames if name not in excluded_dirs]
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                if not os.path.isfile(full_path):
                    continue
                rel_path = os.path.relpath(full_path, session_root)
                with open(full_path, "rb") as handle:
                    content = base64.b64encode(handle.read()).decode("ascii")
                files.append({"path": rel_path.replace(os.sep, "/"), "data_b64": content})
        return files

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
        if normalized_provider == "codex":
            _seed_codex_auth_from_global(auth_home, env=env)
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
        state = store["read_session_state"](name)
        if not state:
            raise CdxError(f"Session state missing for {name}. Reconnect required.")
        now = _local_now_iso()
        store["write_session_state"](name, {**state, "rehydratedAt": now})
        return store["update_session"](name, lambda s: {
            **s, "updatedAt": now, "lastLaunchedAt": now
        })

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
        if (
            session["provider"] == "codex"
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

    def export_bundle(file_path, include_auth=False, session_names=None, passphrase=None, force=False):
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
        for session in sessions:
            payload["sessions"].append(_build_export_session_record(session))
            state = store["read_session_state"](session["name"])
            if state is not None:
                payload["states"][session["name"]] = state
            if include_auth:
                session_root = session.get("sessionRoot") or _get_session_root(session["name"])
                payload["profiles"][session["name"]] = _collect_profile_files(session_root)

        bundle_bytes = encode_bundle(payload, include_auth=include_auth, passphrase=passphrase)
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
        "ensure_session_state": ensure_session_state,
        "list_sessions": list_sessions,
        "get_session": get_session,
        "record_status": record_status,
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
