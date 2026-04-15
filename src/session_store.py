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
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def _file_lock(lock_path):
    _ensure_dir(os.path.dirname(lock_path))
    with open(lock_path, "a", encoding="utf-8") as lock:
        try:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        try:
            yield
        finally:
            try:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass


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

    def _mutate_sessions(mutator):
        with _file_lock(lock_file):
            sessions = _load()
            result = mutator(sessions)
            _save(sessions)
            return result

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
        def mutator(sessions):
            if any(s.get("name") == session["name"] for s in sessions):
                return {"ok": False, "session": None}
            sessions.append(session)
            return {"ok": True, "session": session}

        result = _mutate_sessions(mutator)
        if not result["ok"]:
            return result
        write_session_state(session["name"], {
            "provider": session["provider"],
            "status": "ready",
            "rehydratedAt": None,
        })
        return result

    def update_session(name, updater):
        def mutator(sessions):
            for i, s in enumerate(sessions):
                if s.get("name") == name:
                    sessions[i] = updater(s)
                    return sessions[i]
            return None

        return _mutate_sessions(mutator)

    def remove_session(name):
        def mutator(sessions):
            for i, s in enumerate(sessions):
                if s.get("name") == name:
                    sessions.pop(i)
                    return s
            return None

        removed = _mutate_sessions(mutator)
        if removed:
            state_path = _state_file_path(name)
            try:
                os.remove(state_path)
            except FileNotFoundError:
                pass
        return removed

    def rename_session(source_name, dest_name, updater):
        def mutator(sessions):
            source_index = None
            for i, s in enumerate(sessions):
                if s.get("name") == source_name:
                    source_index = i
                elif s.get("name") == dest_name:
                    return {"ok": False, "session": None, "reason": "exists"}
            if source_index is None:
                return {"ok": False, "session": None, "reason": "missing"}

            updated = updater(sessions[source_index])
            sessions[source_index] = updated
            return {"ok": True, "session": updated, "reason": None}

        result = _mutate_sessions(mutator)
        if not result["ok"]:
            return result
        source_state_path = _state_file_path(source_name)
        dest_state_path = _state_file_path(dest_name)
        try:
            os.replace(source_state_path, dest_state_path)
        except FileNotFoundError:
            pass
        return result

    def replace_session(name, session):
        def mutator(sessions):
            for i, existing in enumerate(sessions):
                if existing.get("name") == name:
                    sessions[i] = session
                    return {"ok": True, "session": session, "replaced": True}
            sessions.append(session)
            return {"ok": True, "session": session, "replaced": False}

        result = _mutate_sessions(mutator)
        write_session_state(session["name"], {
            "provider": session["provider"],
            "status": "ready",
            "rehydratedAt": None,
        })
        return result

    def read_session_state(name):
        return _read_json(_state_file_path(name), None)

    def write_session_state(name, state):
        _write_json(_state_file_path(name), state)

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
