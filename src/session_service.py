#!/usr/bin/env python3
"""Session service: session CRUD, launch settings, runtime, auth, and assembly.

`create_session_service` returns the interface dict every caller uses; the
functions behind it live here, or in one of the modules this re-exports from.

Why the split stops here. `req_027` measured the coupling between the six
concern groups by transitive closure and cut only where it was real:

    group      entry lines   helpers reached only from it
    status             264   16     -> src/session_status.py
    backup             179    9     -> src/session_backup.py
    crud               235    3     stays
    settings            58    1     stays
    runtime            115    0     stays
    auth                10    0     stays

`runtime` and `auth` have **no** helper of their own. Made into modules they
would be thin wrappers over imports from here, which reads worse than leaving
them in place; `crud` is the core the others build on. If you are about to
finish the job by splitting the remaining four, re-measure first - that is the
evidence that says not to.

The `# noqa: F401` markers below are load-bearing: without them ruff removes
the re-exports as unused and callers importing through this module break.
`test_session_service_facade_still_exposes_every_name_its_callers_import`
guards that.
"""
import json
import os
import shutil
import tempfile
import uuid
from functools import partial

from .codex_usage import fetch_codex_rate_limits
from .config import (
    MAX_LAUNCH_BUDGET_USD,
    MAX_LAUNCH_EXTRA_ARGS_LENGTH,
    PERMISSION_INPUT_VALUES,
    PERMISSION_VALUES,
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    REASONING_EFFORT_VALUES,
    get_cdx_home,
    normalize_permission,
    split_extra_args,
)
from .errors import CdxError
from .fs_utils import atomic_write, remove_tree
from .session_backup import (  # noqa: F401  (re-exported for callers and tests)
    _FORCE_IMPORT_PRESERVED_PROFILE_PATHS,
    _auth_bundle_paths,
    _build_export_session_record,
    _collect_auth_files,
    _force_import_preserved_profile_paths,
    _resolve_session_subset,
    _restore_force_import_profile_paths,
    _restore_import_backup,
    _safe_relpath,
    _validate_import_profile_files,
    export_bundle,
    import_bundle,
)
from .session_helpers import (  # noqa: F401  (re-exported for src/__init__.py, callers and tests)
    ALLOWED_PROVIDERS,
    DEFAULT_PROVIDER,
    MAX_SESSION_NAME_LENGTH,
    RESERVED_SESSION_NAMES,
    _encode,
    _ensure_private_dir,
    _get_global_codex_home,
    _get_session_auth_home,
    _get_session_root,
    _local_now_iso,
    _normalize_provider,
    _process_is_running,
    _runtime_is_active,
    _session_runtime,
    _validate_new_session_name,
    list_sessions,
)
from .session_status import (  # noqa: F401  (re-exported for callers and tests)
    CLAUDE_STATUS_CACHE_TTL_SECONDS,
    CODEX_STATUS_CACHE_TTL_SECONDS,
    MAX_STATUS_WORKERS,
    STATUS_CACHE_TTL_SECONDS,
    _compute_available_pct,
    _fetch_codex_status,
    _is_low_confidence_status_source,
    _is_status_cache_fresh,
    _is_status_newer,
    _merge_status_payload,
    _normalize_pct_value,
    _normalize_status_payload,
    _parse_status_timestamp,
    _read_expected_account_email,
    _resolve_row_session,
    _resolve_session_status,
    _row_priority,
    _row_reasoning_effort,
    _status_cache_hit,
    _status_cache_ttl_seconds,
    _status_has_more_detail,
    _status_row_from_session,
    _to_local_iso,
    format_list_rows,
    get_status_row,
    get_status_rows,
    record_status,
)
from .session_store import create_session_store
from .status_source import find_latest_codex_conversation_id

MAX_SESSION_LABEL_LENGTH = 64
# Each live Codex probe spawns app-server, which can refresh+rotate the OAuth
# token. Cache longer so routine status calls don't keep triggering refreshes.
STATUS_PROBE_TIMEOUT_SECONDS = 5
# References to the shared definitions in config, not copies. These used to be
# three separate literals here, validated independently of the ones `cdx run`
# uses, which is how `cdx set` and `cdx run` came to disagree about the same
# setting.
LAUNCH_POWER_VALUES = REASONING_EFFORT_VALUES
LAUNCH_REASONING_EFFORT_VALUES = REASONING_EFFORT_VALUES
LAUNCH_PERMISSION_VALUES = PERMISSION_VALUES
MAX_LAUNCH_MODEL_LENGTH = 128
MIN_LAUNCH_PRIORITY = 0
MAX_LAUNCH_PRIORITY = 100
DEFAULT_LAUNCH_SETTINGS = {
    "power": "medium",
    "fast": False,
}


def _seed_codex_auth_from_global(auth_home, env=None):
    source_home = _get_global_codex_home(env)
    source_auth = os.path.join(source_home, "auth.json")
    dest_auth = os.path.join(auth_home, "auth.json")
    if source_home == auth_home or os.path.exists(dest_auth) or not os.path.isfile(source_auth):
        return False
    shutil.copy2(source_auth, dest_auth)
    return True


def _normalize_launch_settings(settings, mark_fast_service_tier=True):
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
        # Accepts the provider-native aliases (workspace-write, read-only,
        # danger-full-access) exactly as `cdx run --permission` does, and stores
        # the canonical value, so nothing downstream has to learn the aliases.
        # They used to work on `run` only, so a value copied from one command to
        # the other was rejected.
        permission = normalize_permission(settings["permission"])
        if permission is None:
            allowed = "|".join(PERMISSION_INPUT_VALUES)
            raise CdxError(
                f"Unsupported permission: {settings['permission']} (allowed values: {allowed})"
            )
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
        if normalized["fast"] is True and mark_fast_service_tier:
            normalized["fastMode"] = "service_tier"
        else:
            normalized.pop("fastMode", None)
        if settings.get("fastMode") == "service_tier" and normalized["fast"] is True:
            normalized["fastMode"] = "service_tier"
    if "rtk" in settings and settings["rtk"] is not None:
        value = settings["rtk"]
        if isinstance(value, bool):
            normalized["rtk"] = value
        else:
            text = str(value).strip().lower()
            if text in ("on", "true", "1", "yes"):
                normalized["rtk"] = True
            elif text in ("off", "false", "0", "no"):
                normalized["rtk"] = False
            else:
                raise CdxError(f"Unsupported rtk value: {settings['rtk']}")
    if "logics" in settings and settings["logics"] is not None:
        value = settings["logics"]
        if isinstance(value, bool):
            normalized["logics"] = value
        else:
            text = str(value).strip().lower()
            if text in ("on", "true", "1", "yes"):
                normalized["logics"] = True
            elif text in ("off", "false", "0", "no"):
                normalized["logics"] = False
            else:
                raise CdxError(f"Unsupported logics value: {settings['logics']}")
    if "model" in settings and settings["model"] is not None:
        model = str(settings["model"]).strip()
        if not model:
            raise CdxError("Model cannot be empty.")
        if len(model) > MAX_LAUNCH_MODEL_LENGTH or any(ord(ch) < 32 or ord(ch) == 127 for ch in model):
            raise CdxError("Model contains unsupported characters.")
        normalized["model"] = model
    if "fallback_model" in settings and settings["fallback_model"] is not None:
        # Claude accepts a comma-separated list here and tries each in order, so
        # this validates every element rather than the string as one model name.
        raw = str(settings["fallback_model"]).strip()
        if not raw:
            raise CdxError("Fallback model cannot be empty.")
        elements = [element.strip() for element in raw.split(",")]
        if any(not element for element in elements):
            raise CdxError("Fallback model cannot contain an empty entry.")
        for element in elements:
            if len(element) > MAX_LAUNCH_MODEL_LENGTH or any(ord(ch) < 32 or ord(ch) == 127 for ch in element):
                raise CdxError("Fallback model contains unsupported characters.")
        normalized["fallback_model"] = ",".join(elements)
    if "extra_args" in settings and settings["extra_args"] is not None:
        extra = str(settings["extra_args"]).strip()
        if not extra:
            raise CdxError("Extra args cannot be empty.")
        if len(extra) > MAX_LAUNCH_EXTRA_ARGS_LENGTH or any(ord(ch) < 32 or ord(ch) == 127 for ch in extra):
            raise CdxError("Extra args contain unsupported characters.")
        # Parsed here, not at launch: a string that cannot be split into argv
        # should be rejected when it is set, not when a run fails days later.
        if split_extra_args(extra) is None:
            raise CdxError("Extra args are not a valid argument list (unbalanced quotes).")
        normalized["extra_args"] = extra
    if "budget" in settings and settings["budget"] is not None:
        try:
            budget = float(settings["budget"])
        except (TypeError, ValueError) as error:
            raise CdxError(f"Unsupported budget: {settings['budget']}") from error
        # NaN fails every comparison below, so it has to be rejected explicitly
        # or it would sail through the range check.
        if budget != budget or budget <= 0 or budget > MAX_LAUNCH_BUDGET_USD:
            raise CdxError(f"Unsupported budget: {settings['budget']}")
        normalized["budget"] = budget
    if "priority" in settings and settings["priority"] is not None:
        try:
            priority = int(settings["priority"])
        except (TypeError, ValueError) as error:
            raise CdxError(f"Unsupported priority: {settings['priority']}") from error
        if priority < MIN_LAUNCH_PRIORITY or priority > MAX_LAUNCH_PRIORITY:
            raise CdxError(f"Unsupported priority: {settings['priority']}")
        normalized["priority"] = priority
    return normalized


def _parse_status_timeout_seconds(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _ensure_claude_attribution_disabled(auth_home):
    settings_dir = os.path.join(auth_home, ".claude")
    settings_path = os.path.join(settings_dir, "settings.json")
    try:
        os.makedirs(settings_dir, exist_ok=True)
        with open(settings_path, encoding="utf-8") as handle:
            settings = json.load(handle)
    except FileNotFoundError:
        settings = {}
    except (OSError, json.JSONDecodeError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    settings["includeCoAuthoredBy"] = False
    try:
        atomic_write(settings_path, json.dumps(settings, indent=2, sort_keys=True) + "\n", mode=0o644)
    except OSError:
        return False
    return True


def _normalize_session_label(label):
    text = str(label or "").strip()
    if not text:
        raise CdxError("Session label is required")
    if len(text) > MAX_SESSION_LABEL_LENGTH:
        raise CdxError(f"Session label is too long (max {MAX_SESSION_LABEL_LENGTH} characters)")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise CdxError("Session label cannot contain control characters")
    return text


def set_launch_settings(store, name, settings):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    updates = _normalize_launch_settings(settings)
    if not updates:
        raise CdxError("At least one launch setting is required.")
    now = _local_now_iso()

    def updater(s):
        # Build the new launch dict from the fresh record inside the store
        # lock; a pre-lock snapshot loses a concurrent setting change.
        current = _normalize_launch_settings(s.get("launch") or {}, mark_fast_service_tier=False)
        launch = {**current, **updates}
        if "power" in updates:
            launch.pop("reasoning_effort", None)
            launch.pop("reasoningEffort", None)
        if "reasoning_effort" in updates:
            launch.pop("power", None)
        explicit_power = "power" in updates or "reasoning_effort" in updates
        if explicit_power and "fast" not in updates and launch.get("fastMode") != "service_tier":
            launch["fast"] = False
            launch.pop("fastMode", None)
        if updates.get("fast") is False:
            launch.pop("fastMode", None)
            if not any(key in launch for key in ("power", "reasoning_effort", "reasoningEffort")):
                launch["power"] = DEFAULT_LAUNCH_SETTINGS["power"]
        return {
            **s,
            "launch": launch,
            "updatedAt": now,
        }

    return store["update_session"](name, updater)

def unset_launch_settings(store, name, keys):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    if not keys:
        raise CdxError("At least one launch setting is required.")
    allowed = {
        "power", "reasoning_effort", "reasoningEffort", "permission", "fast", "rtk", "logics",
        "model", "fallback_model", "budget", "extra_args", "priority",
    }
    unknown = [key for key in keys if key not in allowed]
    if unknown:
        raise CdxError(f"Unsupported launch setting: {', '.join(unknown)}")
    now = _local_now_iso()

    def updater(s):
        current = dict(s.get("launch") or {})
        for key in keys:
            current.pop(key, None)
        updated = {**s, "updatedAt": now}
        if current:
            updated["launch"] = current
        else:
            updated.pop("launch", None)
        return updated

    return store["update_session"](name, updater)

def update_auth_state(store, name, updater):
    now = _local_now_iso()
    updated = store["update_session"](name, lambda s: {
        **s,
        "updatedAt": now,
        "auth": updater(s.get("auth") or {}),
    })
    if not updated:
        raise CdxError(f"Unknown session: {name}")
    return updated


def get_session(store, name):
    return store["get_session"](name)


def ensure_session_state(store, name):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    result = {}

    def updater(state):
        if state:
            result["state"] = state
            return None
        repaired = {
            "provider": session["provider"],
            "status": "ready",
            "rehydratedAt": None,
        }
        result["state"] = repaired
        return repaired

    store["update_session_state"](name, updater)
    return result["state"]


def set_session_label(store, name, label):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    normalized = _normalize_session_label(label)
    now = _local_now_iso()
    return store["update_session"](name, lambda s: {
        **s,
        "label": normalized,
        "updatedAt": now,
    })


def clear_session_label(store, name):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    now = _local_now_iso()

    def updater(s):
        updated = {**s, "updatedAt": now}
        updated.pop("label", None)
        return updated

    return store["update_session"](name, updater)


def set_session_enabled(store, name, enabled):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    now = _local_now_iso()
    return store["update_session"](name, lambda s: {
        **s,
        "enabled": bool(enabled),
        "updatedAt": now,
    })


def remove_session(base_dir, store, name):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    session_root = session.get("sessionRoot") or _get_session_root(base_dir, name)
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
            remove_tree(quarantine_root)
        except OSError as error:
            raise CdxError(
                f"Removed session {name}, but failed to delete archived profile {quarantine_root}: {error}"
            ) from error
    return removed


def copy_session(base_dir, store, source_name, dest_name):
    if source_name == dest_name:
        raise CdxError("Source and destination session names must be different")
    _validate_new_session_name(dest_name)
    source = store["get_session"](source_name)
    if not source:
        raise CdxError(f"Unknown session: {source_name}")
    existing = store["get_session"](dest_name)
    overwritten = False
    source_root = source.get("sessionRoot") or _get_session_root(base_dir, source_name)
    dest_root = _get_session_root(base_dir, dest_name)
    if not existing and os.path.exists(dest_root):
        raise CdxError(f"Session profile already exists: {dest_name}")
    dest_auth_home = _get_session_auth_home(base_dir, dest_name, source["provider"])
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
        **({"label": source.get("label")} if source.get("label") else {}),
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
            remove_tree(dest_root, ignore_errors=True)
        if backup_root and os.path.exists(backup_root) and not os.path.exists(dest_root):
            os.rename(backup_root, dest_root)
        raise
    finally:
        if backup_root and os.path.exists(backup_root):
            remove_tree(backup_root, ignore_errors=True)
        remove_tree(temp_parent, ignore_errors=True)
    if not result["ok"]:
        raise CdxError(f"Failed to create session: {dest_name}")
    return {"session": result["session"], "overwritten": overwritten}


def rename_session(base_dir, store, source_name, dest_name):
    if source_name == dest_name:
        raise CdxError("Source and destination session names must be different")
    _validate_new_session_name(dest_name)
    source = store["get_session"](source_name)
    if not source:
        raise CdxError(f"Unknown session: {source_name}")
    if store["get_session"](dest_name):
        raise CdxError(f"Session already exists: {dest_name}")

    source_root = source.get("sessionRoot") or _get_session_root(base_dir, source_name)
    dest_root = _get_session_root(base_dir, dest_name)
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
            "authHome": _get_session_auth_home(base_dir, dest_name, s["provider"]),
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


def create_session(base_dir, env, store, name, provider=DEFAULT_PROVIDER):
    _validate_new_session_name(name)
    normalized_provider = _normalize_provider(provider)
    session_root = _get_session_root(base_dir, name)
    auth_home = _get_session_auth_home(base_dir, name, normalized_provider)
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
        "launch": dict(DEFAULT_LAUNCH_SETTINGS),
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


def record_launch_history(store, name, payload):
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
    _observe_codex_conversation(store, session)
    return entry


def _observe_codex_conversation(store, session):
    """Read Codex's conversation id back after a run, if it wrote one.

    Codex mints the id itself, so unlike Claude this can only be observed once
    the rollout exists. Failing to find one is normal and leaves the session on
    the recency resume path; it is never an error worth surfacing to a launch
    that otherwise succeeded.
    """
    if session.get("provider") != PROVIDER_CODEX:
        return
    auth_home = session.get("authHome")
    if not auth_home:
        return
    try:
        identifier = find_latest_codex_conversation_id(auth_home)
    except OSError:
        return
    if not identifier or identifier == (session.get("conversation") or {}).get("id"):
        return
    store["update_session"](session["name"], lambda s: {
        **s,
        "conversation": {
            "id": identifier,
            "provenance": "observed",
            "recordedAt": _local_now_iso(),
        },
    })


def get_launch_history(store, name=None, limit=20):
    if name and not store["get_session"](name):
        raise CdxError(f"Unknown session: {name}")
    return store["list_launch_history"](session_name=name, limit=limit)


def start_session_runtime(store, name, payload=None):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
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

    def updater(state):
        if not state:
            raise CdxError(f"Session state missing for {name}. Reconnect required.")
        return {
            **state,
            "status": "running",
            "runtime": runtime,
        }

    store["update_session_state"](name, updater)
    return runtime


def finish_session_runtime(store, name, run_id=None, payload=None):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    payload = dict(payload or {})
    outcome = {}

    def updater(state):
        if not state:
            return None
        runtime = state.get("runtime") or {}
        if run_id and runtime.get("runId") != run_id:
            outcome["runtime"] = runtime
            return None
        updated_runtime = {
            **runtime,
            "status": payload.get("status") or "stopped",
            "endedAt": payload.get("endedAt") or _local_now_iso(),
        }
        if "returncode" in payload:
            updated_runtime["returncode"] = payload["returncode"]
        outcome["runtime"] = updated_runtime
        return {
            **state,
            "status": "ready",
            "runtime": updated_runtime,
        }

    store["update_session_state"](name, updater)
    return outcome.get("runtime")


def launch_session(store, name):
    session = store["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    if session.get("enabled", True) is False:
        raise CdxError(f"Session is disabled: {name}")
    now = _local_now_iso()

    def state_updater(state):
        if not state:
            raise CdxError(f"Session state missing for {name}. Reconnect required.")
        return {**state, "rehydratedAt": now}

    store["update_session_state"](name, state_updater)

    def session_updater(s):
        updated = {**s, "updatedAt": now, "lastLaunchedAt": now}
        conversation = _conversation_identity_for_launch(s)
        if conversation:
            updated["conversation"] = conversation
        return updated

    return store["update_session"](name, session_updater)


def _conversation_identity_for_launch(session):
    """The conversation id this launch will carry, or None to leave it alone.

    Claude accepts a caller-supplied `--session-id`, so cdx mints one here,
    before the launch spec is built, and knows the conversation's identity
    without having to find it afterwards. A fresh id per launch rather than one
    reused forever: a launch starts a new conversation, and `cdx resume` should
    mean the last one, so the stored value is always the newest. Reusing a
    single id across launches would also depend on how the provider treats a
    repeated `--session-id`, which is a behaviour cdx does not need to rely on.

    Codex has no equivalent flag; its identity is read back from the rollout
    after the run, so nothing is minted here.
    """
    if session.get("provider") != PROVIDER_CLAUDE:
        return None
    return {
        "id": str(uuid.uuid4()),
        "provenance": "imposed",
        "recordedAt": _local_now_iso(),
    }


def get_session_root(base_dir, name):
    return _get_session_root(base_dir, name)


def get_session_auth_home(base_dir, name, provider):
    return _get_session_auth_home(base_dir, name, provider)


def create_session_service(options=None):
    if options is None:
        options = {}
    env = options.get("env", os.environ)
    base_dir = options.get("base_dir") or get_cdx_home(env)
    store = options.get("store") or create_session_store(base_dir)
    custom_codex_status_fetcher = options.get("fetchCodexRateLimits")
    codex_status_fetcher = custom_codex_status_fetcher or fetch_codex_rate_limits
    default_status_timeout_seconds = (
        _parse_status_timeout_seconds(options.get("statusTimeoutSeconds"))
        or _parse_status_timeout_seconds(env.get("CDX_STATUS_TIMEOUT_SECONDS"))
        or STATUS_PROBE_TIMEOUT_SECONDS
    )

    # None when there is no fetcher, so callers test the callable they were
    # given rather than a separate flag they would also have to be passed.
    fetch_codex_status = partial(
        _fetch_codex_status,
        codex_status_fetcher,
        custom_codex_status_fetcher,
        default_status_timeout_seconds,
    ) if codex_status_fetcher else None

    return {
        "create_session": partial(create_session, base_dir, env, store),
        "remove_session": partial(remove_session, base_dir, store),
        "copy_session": partial(copy_session, base_dir, store),
        "rename_session": partial(rename_session, base_dir, store),
        "launch_session": partial(launch_session, store),
        "active_session_runtime": partial(_session_runtime, store),
        "start_session_runtime": partial(start_session_runtime, store),
        "finish_session_runtime": partial(finish_session_runtime, store),
        "ensure_session_state": partial(ensure_session_state, store),
        "list_sessions": partial(list_sessions, store),
        "get_session": partial(get_session, store),
        "set_session_enabled": partial(set_session_enabled, store),
        "set_session_label": partial(set_session_label, store),
        "clear_session_label": partial(clear_session_label, store),
        "set_launch_settings": partial(set_launch_settings, store),
        "unset_launch_settings": partial(unset_launch_settings, store),
        "record_status": partial(record_status, store),
        "record_launch_history": partial(record_launch_history, store),
        "get_launch_history": partial(get_launch_history, store),
        "update_auth_state": partial(update_auth_state, store),
        "get_status_row": partial(get_status_row, store, base_dir, env, fetch_codex_status),
        "get_status_rows": partial(get_status_rows, store, base_dir, env, fetch_codex_status),
        "format_list_rows": partial(format_list_rows, store),
        "get_session_auth_home": partial(get_session_auth_home, base_dir),
        "get_session_root": partial(get_session_root, base_dir),
        "export_bundle": partial(export_bundle, base_dir, store),
        "import_bundle": partial(import_bundle, base_dir, store),
        "base_dir": base_dir,
        "normalize_provider": _normalize_provider,
    }
