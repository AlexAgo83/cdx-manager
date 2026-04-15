import json
import os
from pathlib import Path


def _ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def _read_json(file_path, fallback):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return fallback


def _write_json(file_path, value):
    _ensure_dir(os.path.dirname(file_path))
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def create_session_store(base_dir):
    store_file = os.path.join(base_dir, "sessions.json")
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

    def list_sessions():
        return sorted(_load(), key=lambda session: session.get("name", ""))

    def get_session(name):
        for s in _load():
            if s.get("name") == name:
                return s
        return None

    def add_session(session):
        sessions = _load()
        if any(s.get("name") == session["name"] for s in sessions):
            return {"ok": False, "session": None}
        sessions.append(session)
        _save(sessions)
        write_session_state(session["name"], {
            "provider": session["provider"],
            "status": "ready",
            "rehydratedAt": None,
        })
        return {"ok": True, "session": session}

    def update_session(name, updater):
        sessions = _load()
        for i, s in enumerate(sessions):
            if s.get("name") == name:
                sessions[i] = updater(s)
                _save(sessions)
                return sessions[i]
        return None

    def remove_session(name):
        sessions = _load()
        for i, s in enumerate(sessions):
            if s.get("name") == name:
                sessions.pop(i)
                _save(sessions)
                state_path = _state_file_path(name)
                try:
                    os.remove(state_path)
                except FileNotFoundError:
                    pass
                return s
        return None

    def rename_session(source_name, dest_name, updater):
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
        sessions[source_index] = updated
        _save(sessions)

        source_state_path = _state_file_path(source_name)
        dest_state_path = _state_file_path(dest_name)
        try:
            os.replace(source_state_path, dest_state_path)
        except FileNotFoundError:
            pass
        return {"ok": True, "session": updated, "reason": None}

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
        "read_session_state": read_session_state,
        "write_session_state": write_session_state,
    }
