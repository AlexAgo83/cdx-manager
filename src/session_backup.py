"""Backup domain: exporting and importing session bundles.

Split out of session_service.py along the second of the two seams the req_027
coupling measurement supports. Moved verbatim; re-exported by session_service.
"""

import base64
import binascii
import os
import shutil
import tempfile

from .backup_bundle import decode_bundle, encode_bundle
from .config import PROVIDER_CLAUDE
from .errors import CdxError
from .fs_utils import atomic_write, remove_tree
from .session_helpers import (
    _encode,
    _ensure_private_dir,
    _get_session_auth_home,
    _get_session_root,
    _local_now_iso,
    _normalize_provider,
    _validate_new_session_name,
    list_sessions,
)

_FORCE_IMPORT_PRESERVED_PROFILE_PATHS = ("plugins",)

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

def _build_export_session_record(session):
    return {
        "name": session["name"],
        "provider": session["provider"],
        "label": session.get("label"),
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

def _validate_import_profile_files(payload, imported_sessions):
    profiles = payload.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise CdxError("Bundle contains invalid profile data.")
    decoded_profiles = {}
    for session_payload in imported_sessions:
        name = session_payload["name"]
        files = []
        profile_items = profiles.get(name, [])
        if not isinstance(profile_items, list):
            raise CdxError(f"Bundle contains invalid profile data for session {name}.")
        for item in profile_items:
            if not isinstance(item, dict):
                raise CdxError(f"Bundle contains invalid profile entry for session {name}.")
            rel_path = _safe_relpath(item.get("path"))
            data_b64 = item.get("data_b64")
            if not isinstance(data_b64, str):
                raise CdxError(f"Bundle contains invalid file data for session {name}: {rel_path}")
            try:
                content = base64.b64decode(data_b64.encode("ascii"), validate=True)
            except (binascii.Error, UnicodeEncodeError) as error:
                raise CdxError(f"Bundle contains invalid file data for session {name}: {rel_path}") from error
            files.append({"path": rel_path, "content": content})
        decoded_profiles[name] = files
    return decoded_profiles

def _force_import_preserved_profile_paths(session_root):
    return [rel_path for rel_path in _FORCE_IMPORT_PRESERVED_PROFILE_PATHS if os.path.exists(os.path.join(session_root, rel_path))]

def _restore_force_import_profile_paths(name, backup_root, session_root, rel_paths):
    if not backup_root:
        return
    for rel_path in rel_paths:
        source_path = os.path.join(backup_root, rel_path)
        dest_path = os.path.join(session_root, rel_path)
        if not os.path.exists(source_path) or os.path.exists(dest_path):
            continue
        try:
            if os.path.isdir(source_path) and not os.path.islink(source_path):
                shutil.copytree(source_path, dest_path)
            else:
                _ensure_private_dir(os.path.dirname(dest_path))
                shutil.copy2(source_path, dest_path)
        except Exception as error:
            raise CdxError(f"Could not restore local plugin state for session {name}: {rel_path}") from error

def _resolve_session_subset(store, session_names):
    if not session_names:
        return list_sessions(store)
    by_name = {session["name"]: session for session in list_sessions(store)}
    selected = []
    for name in session_names:
        session = by_name.get(name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        selected.append(session)
    return selected

def _restore_import_backup(store, name, backup_root, session_root, old_record, old_state):
    if os.path.exists(session_root):
        remove_tree(session_root, ignore_errors=True)
    if backup_root and os.path.exists(backup_root):
        os.rename(backup_root, session_root)
    if old_record:
        store["replace_session"](name, old_record)
        if old_state is not None:
            store["write_session_state"](name, old_state)
    else:
        store["remove_session"](name)

def export_bundle(base_dir, store, file_path, include_auth=False, session_names=None, passphrase=None, force=False, progress_callback=None):
    if not file_path:
        raise CdxError("Export path is required.")
    if os.path.exists(file_path) and not force:
        raise CdxError(f"Export path already exists: {file_path}")

    sessions = _resolve_session_subset(store, session_names)
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
            session_root = session.get("sessionRoot") or _get_session_root(base_dir, session["name"])
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
    # Atomic + 0o600 from the start: the export path may live in a
    # world-traversable directory, and a crash must not clobber a
    # previous good bundle with a truncated one.
    atomic_write(os.path.abspath(file_path), bundle_bytes, mode=0o600)
    return {
        "path": file_path,
        "include_auth": include_auth,
        "session_names": [session["name"] for session in sessions],
        "session_count": len(sessions),
        "profile_file_count": profile_file_count if include_auth else None,
        "profile_bytes": profile_bytes if include_auth else None,
        "bundle_size_bytes": len(bundle_bytes),
    }

def import_bundle(base_dir, store, file_path,
    passphrase=None,
    session_names=None,
    force=False,
    merge=False,
    allow_authless_force=False,):
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

    existing = {session["name"] for session in list_sessions(store)}
    conflicts = [name for name in names if name in existing]
    if conflicts and not force and not merge:
        raise CdxError(f"Import would overwrite existing sessions: {', '.join(conflicts)}")
    if conflicts and force and not decoded["meta"].get("include_auth") and not allow_authless_force:
        raise CdxError(
            "Import --force would overwrite existing session credentials, but this bundle has no auth payloads. "
            "Re-export with --include-auth, use --merge, or pass --allow-authless-force to discard local credentials."
        )

    for session_payload in imported_sessions:
        _validate_new_session_name(session_payload["name"])
        _normalize_provider(session_payload["provider"])
    decoded_profiles = _validate_import_profile_files(payload, imported_sessions)

    for session_payload in imported_sessions:
        name = session_payload["name"]
        provider = _normalize_provider(session_payload["provider"])
        is_existing = name in existing

        session_root = _get_session_root(base_dir, name)
        auth_home = _get_session_auth_home(base_dir, name, provider)
        _ensure_private_dir(base_dir)
        _ensure_private_dir(os.path.join(base_dir, "profiles"))
        backup_root = None
        old_record = None
        old_state = None
        preserved_profile_paths = []
        if is_existing and force:
            old_record = store["get_session"](name)
            old_state = store["read_session_state"](name)
            preserved_profile_paths = _force_import_preserved_profile_paths(session_root)
            if os.path.exists(session_root):
                backup_root = tempfile.mkdtemp(prefix=f".{_encode(name)}.import.", dir=os.path.dirname(session_root))
                os.rmdir(backup_root)
                os.rename(session_root, backup_root)
            is_existing = False
        _ensure_private_dir(session_root)
        _ensure_private_dir(auth_home)

        existing_state_before = None
        try:
            if is_existing and merge:
                existing_record = store["get_session"](name) or {}
                # replace_session resets the state file to defaults, so the
                # local state must be captured before it runs.
                existing_state_before = store["read_session_state"](name) or {}
                bundle_record = {
                    **session_payload,
                    "provider": provider,
                    "enabled": session_payload.get("enabled", True) is not False,
                    "sessionRoot": session_root,
                    "authHome": auth_home,
                }
                # Existing values take precedence; bundle fills in missing keys only.
                merged_record = {**bundle_record, **{k: v for k, v in existing_record.items() if v is not None}}
                merged_record["sessionRoot"] = session_root
                merged_record["authHome"] = auth_home
                store["replace_session"](name, merged_record)
            else:
                session_record = {
                    **session_payload,
                    "provider": provider,
                    "enabled": session_payload.get("enabled", True) is not False,
                    "sessionRoot": session_root,
                    "authHome": auth_home,
                }
                store["replace_session"](name, session_record)

            state = (payload.get("states") or {}).get(name)
            if is_existing and merge:
                merged_state = {**(state or {}), **{k: v for k, v in (existing_state_before or {}).items() if v is not None}}
                if merged_state:
                    store["write_session_state"](name, merged_state)
            elif state is not None:
                store["write_session_state"](name, state)

            for item in decoded_profiles.get(name, []):
                dest_path = os.path.join(session_root, item["path"])
                # In merge mode, skip files that already exist locally.
                if is_existing and merge and os.path.exists(dest_path):
                    continue
                _ensure_private_dir(os.path.dirname(dest_path))
                # Decrypted credentials: 0o600 from creation, no umask window.
                atomic_write(dest_path, item["content"], mode=0o600)
            _restore_force_import_profile_paths(name, backup_root, session_root, preserved_profile_paths)
        except Exception:
            _restore_import_backup(store, name, backup_root, session_root, old_record, old_state)
            raise
        finally:
            if backup_root and os.path.exists(backup_root):
                remove_tree(backup_root, ignore_errors=True)

    return {
        "path": file_path,
        "session_names": names,
        "include_auth": bool(decoded["meta"].get("include_auth")),
    }
