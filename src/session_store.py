import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .errors import CdxError


def _ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def _read_json(file_path, fallback):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return fallback
    except json.JSONDecodeError as error:
        raise CdxError(f"Corrupt JSON file: {file_path}") from error


def _write_json(file_path, value):
    directory = os.path.dirname(file_path)
    _ensure_dir(directory)
    fd, temp_path = tempfile.mkstemp(prefix=f".{os.path.basename(file_path)}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, file_path)
        _fsync_directory(directory)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(directory):
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _file_lock(lock_path):
    import sys
    _ensure_dir(os.path.dirname(lock_path))
    with open(lock_path, "a", encoding="utf-8") as lock:
        if sys.platform == "win32":
            import msvcrt
            try:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            except OSError as error:
                raise CdxError(f"Failed to lock session store: {error}") from error
            try:
                yield
            finally:
                try:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError as error:
                    raise CdxError(f"Failed to unlock session store: {error}") from error
        else:
            try:
                import fcntl
            except ImportError as error:
                raise CdxError("Session store locking requires fcntl on this platform") from error
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            except OSError as error:
                raise CdxError(f"Failed to lock session store: {error}") from error
            try:
                yield
            finally:
                try:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                except OSError as error:
                    raise CdxError(f"Failed to unlock session store: {error}") from error


def create_session_store(base_dir):
    store_file = os.path.join(base_dir, "sessions.json")
    lock_file = os.path.join(base_dir, ".sessions.lock")
    state_dir = os.path.join(base_dir, "state")

    def _state_file_path(name):
        return os.path.join(state_dir, f"{_encode(name)}.json")

    def _encode(name):
        from urllib.parse import quote
        return quote(name, safe="")

    def _load():
        data = _read_json(store_file, {"version": 1, "sessions": []})
        return data.get("sessions", [])

    def _save(sessions):
        _write_json(store_file, {"version": 1, "sessions": sessions})

    def _read_session_state_unlocked(name):
        return _read_json(_state_file_path(name), None)

    def _write_session_state_unlocked(name, state):
        _write_json(_state_file_path(name), state)

    def _remove_session_state_unlocked(name):
        try:
            os.remove(_state_file_path(name))
        except FileNotFoundError:
            pass

    def _default_state(session):
        return {
            "provider": session["provider"],
            "status": "ready",
            "rehydratedAt": None,
        }

    def list_sessions():
        with _file_lock(lock_file):
            return sorted(_load(), key=lambda session: session.get("name", ""))

    def get_session(name):
        with _file_lock(lock_file):
            for s in _load():
                if s.get("name") == name:
                    return s
        return None

    def add_session(session):
        with _file_lock(lock_file):
            sessions = _load()
            if any(s.get("name") == session["name"] for s in sessions):
                return {"ok": False, "session": None}
            _write_session_state_unlocked(session["name"], _default_state(session))
            sessions.append(session)
            try:
                _save(sessions)
            except Exception:
                _remove_session_state_unlocked(session["name"])
                raise
            return {"ok": True, "session": session}

    def update_session(name, updater):
        with _file_lock(lock_file):
            sessions = _load()
            for i, s in enumerate(sessions):
                if s.get("name") == name:
                    sessions[i] = updater(s)
                    _save(sessions)
                    return sessions[i]
            return None

    def remove_session(name):
        with _file_lock(lock_file):
            sessions = _load()
            for i, s in enumerate(sessions):
                if s.get("name") == name:
                    removed = sessions.pop(i)
                    old_state = _read_session_state_unlocked(name)
                    _remove_session_state_unlocked(name)
                    try:
                        _save(sessions)
                    except Exception:
                        if old_state is not None:
                            _write_session_state_unlocked(name, old_state)
                        raise
                    return removed
            return None

    def rename_session(source_name, dest_name, updater):
        with _file_lock(lock_file):
            sessions = _load()
            source_index = None
            for i, s in enumerate(sessions):
                if s.get("name") == source_name:
                    source_index = i
                elif s.get("name") == dest_name:
                    return {"ok": False, "session": None, "reason": "exists"}
            if source_index is None:
                return {"ok": False, "session": None, "reason": "missing"}

            updated = updater(sessions[source_index])
            source_state_path = _state_file_path(source_name)
            dest_state_path = _state_file_path(dest_name)
            moved_state = False
            try:
                os.replace(source_state_path, dest_state_path)
                moved_state = True
            except FileNotFoundError:
                pass
            sessions[source_index] = updated
            try:
                _save(sessions)
            except Exception:
                if moved_state:
                    os.replace(dest_state_path, source_state_path)
                raise
            return {"ok": True, "session": updated, "reason": None}

    def replace_session(name, session):
        with _file_lock(lock_file):
            sessions = _load()
            old_state = _read_session_state_unlocked(name)
            old_session = None
            replaced = False
            for i, existing in enumerate(sessions):
                if existing.get("name") == name:
                    old_session = existing
                    sessions[i] = session
                    replaced = True
                    break
            if not replaced:
                sessions.append(session)
            _write_session_state_unlocked(session["name"], _default_state(session))
            try:
                _save(sessions)
            except Exception:
                if old_state is None:
                    _remove_session_state_unlocked(session["name"])
                else:
                    _write_session_state_unlocked(session["name"], old_state)
                if old_session is not None:
                    for i, existing in enumerate(sessions):
                        if existing.get("name") == name:
                            sessions[i] = old_session
                            break
                raise
            return {"ok": True, "session": session, "replaced": replaced}

    def read_session_state(name):
        with _file_lock(lock_file):
            return _read_session_state_unlocked(name)

    def write_session_state(name, state):
        with _file_lock(lock_file):
            _write_session_state_unlocked(name, state)

    return {
        "list_sessions": list_sessions,
        "get_session": get_session,
        "add_session": add_session,
        "update_session": update_session,
        "remove_session": remove_session,
        "rename_session": rename_session,
        "replace_session": replace_session,
        "read_session_state": read_session_state,
        "write_session_state": write_session_state,
    }
