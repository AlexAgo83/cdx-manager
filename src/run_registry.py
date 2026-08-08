import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def registry_path(base_dir):
    return os.path.join(base_dir, "runs.json")


@contextmanager
def _registry_lock(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "a") as handle:
        if sys.platform == "win32":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _read_registry(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {"schema_version": 1, "runs": []}
    if not isinstance(data, dict):
        return {"schema_version": 1, "runs": []}
    runs = data.get("runs")
    if not isinstance(runs, list):
        runs = []
    return {"schema_version": int(data.get("schema_version") or 1), "runs": [run for run in runs if isinstance(run, dict)]}


def _write_registry(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".runs-", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def _is_pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _completed_after(run, since):
    """True when this run finished strictly after `since`.

    `since` is timezone-aware (the CLI resolves it in local time); stored
    timestamps are UTC with a `Z` suffix. A record with an unparseable or
    missing `ended_at` is treated as not-yet-completed rather than matching, so
    a corrupt row cannot be reported as freshly finished on every poll.
    """
    ended_at = run.get("ended_at")
    if not ended_at:
        return False
    try:
        ended = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=timezone.utc)
    return ended > since


def _refresh_stale_runs(data):
    now = utc_now_iso()
    changed = False
    for run in data["runs"]:
        if run.get("status") != "running":
            continue
        pid = run.get("pid")
        if pid and _is_pid_alive(pid):
            continue
        run["status"] = "stale"
        run["ended_at"] = now
        run["error"] = {"code": "stale_process", "message": "Run was marked running but no live provider process was found."}
        changed = True
    return changed


def _base_record(run_id, *, kind, session, provider, model, cwd, artifacts=None):
    return {
        "run_id": run_id,
        "kind": kind or "assistant",
        "status": "running",
        "session": session,
        "provider": provider,
        "model": model,
        "cwd": os.path.abspath(cwd),
        # The manager process drives the run synchronously, so its own pid is
        # the liveness proxy until finish() records the provider child's pid.
        "pid": os.getpid(),
        "started_at": utc_now_iso(),
        # A failover run occupies several sessions in turn while staying one
        # run. `session` and `provider` above name the current occupant so every
        # existing reader keeps working; this is the ordered history behind
        # them, and it exists from the start so no run is ever written in a
        # shape the reporting cannot express.
        "occupancies": [{
            "session": session,
            "provider": provider,
            "started_at": utc_now_iso(),
            "ended_at": None,
            "reason": "initial_selection",
        }],
        "ended_at": None,
        "duration_seconds": None,
        "exit_code": None,
        "usage": None,
        "artifacts": dict(artifacts or {}),
        # Which mechanism is carrying a detached run, and the provider's own
        # handle when it is the provider's. Present on every record so a reader
        # never has to infer it from absence.
        "background_path": None,
        "provider_session_id": None,
        "error": None,
        "task_report": None,
        "final_payload": None,
    }


class RunRegistry:
    def __init__(self, base_dir):
        self.path = registry_path(base_dir)

    def start(self, run_id, *, kind, session, provider, model, cwd, artifacts=None):
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            data["runs"] = [run for run in data["runs"] if run.get("run_id") != run_id]
            record = _base_record(run_id, kind=kind, session=session, provider=provider, model=model, cwd=cwd, artifacts=artifacts)
            data["runs"].insert(0, record)
            _write_registry(self.path, data)
        return record

    def set_pid(self, run_id, pid):
        """Point a registered run at the process actually doing the work.

        `start()` records the caller's own pid, which is right when that caller
        stays to supervise. A detached launch does not: it returns immediately,
        so its pid dies within seconds and `_refresh_stale_runs` would find no
        live process, mark the run `stale`, and stamp an `ended_at` — reporting
        a run that is still going as finished, including to `list(since=...)`.
        """
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            for run in data["runs"]:
                if run.get("run_id") == run_id:
                    run["pid"] = pid
                    _write_registry(self.path, data)
                    return run
        return None

    def record_background(self, run_id, *, path, provider_session_id=None):
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            for run in data["runs"]:
                if run.get("run_id") != run_id:
                    continue
                run["background_path"] = path
                run["provider_session_id"] = provider_session_id
                _write_registry(self.path, data)
                return run
            return None

    def migrate(self, run_id, *, session, provider, reason):
        """Move a still-running run onto another session, keeping one run_id.

        Closes the current occupancy with the reason it ended and opens the
        next one. The top-level `session`/`provider` follow the new occupant so
        readers that know nothing about occupancies stay correct.
        """
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            now = utc_now_iso()
            for run in data["runs"]:
                if run.get("run_id") != run_id:
                    continue
                occupancies = run.get("occupancies") or []
                if occupancies and occupancies[-1].get("ended_at") is None:
                    occupancies[-1]["ended_at"] = now
                    occupancies[-1]["reason"] = reason
                occupancies.append({
                    "session": session,
                    "provider": provider,
                    "started_at": now,
                    "ended_at": None,
                    "reason": "failover_target",
                })
                run["occupancies"] = occupancies
                run["session"] = session
                run["provider"] = provider
                _write_registry(self.path, data)
                return run
            return None

    def finish(self, run_id, *, status, final_payload=None, run_info=None, error=None, task_report=None):
        with _registry_lock(self.path):
            return self._finish_locked(run_id, status=status, final_payload=final_payload, run_info=run_info, error=error, task_report=task_report)

    def _finish_locked(self, run_id, *, status, final_payload=None, run_info=None, error=None, task_report=None):
        data = _read_registry(self.path)
        now = utc_now_iso()
        for run in data["runs"]:
            if run.get("run_id") != run_id:
                continue
            run["status"] = status
            run["ended_at"] = now
            occupancies = run.get("occupancies") or []
            if occupancies and occupancies[-1].get("ended_at") is None:
                occupancies[-1]["ended_at"] = now
                occupancies[-1]["reason"] = status
            if run.get("started_at"):
                try:
                    start = datetime.fromisoformat(str(run["started_at"]).replace("Z", "+00:00"))
                    end = datetime.fromisoformat(now.replace("Z", "+00:00"))
                    run["duration_seconds"] = (end - start).total_seconds()
                except ValueError:
                    run["duration_seconds"] = None
            if run_info:
                run["pid"] = run_info.get("pid")
                run["exit_code"] = run_info.get("returncode")
                run["artifacts"] = {
                    **(run.get("artifacts") or {}),
                    "transcript_path": run_info.get("transcript_path"),
                    "stdout_path": run_info.get("stdout_path"),
                    "stderr_path": run_info.get("stderr_path"),
                }
            if final_payload:
                run["usage"] = final_payload.get("usage")
                run["final_payload"] = final_payload
            if error:
                run["error"] = error
            if task_report:
                run["task_report"] = task_report
            _write_registry(self.path, data)
            return run
        return None

    def list(self, limit=20, since=None):
        """Recent runs, newest first.

        `since` selects every run that *completed* strictly after that moment
        and bypasses `limit` entirely. A cursor caller is asking "what finished
        since I last looked"; capping that by row count would hand back a
        truncated answer that looks complete, which is the silent miss the
        cursor exists to remove. Runs still in flight have no completion time
        and are excluded — they will be returned by a later call, once they
        have actually completed.
        """
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            changed = _refresh_stale_runs(data)
            if changed:
                _write_registry(self.path, data)
        runs = data["runs"]
        if since is not None:
            return [run for run in runs if _completed_after(run, since)]
        return runs[: max(0, int(limit or 20))]

    def get(self, run_id):
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            changed = _refresh_stale_runs(data)
            if changed:
                _write_registry(self.path, data)
        for run in data["runs"]:
            if run.get("run_id") == run_id:
                return run
        return None


def read_text_file(path, limit=120000):
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def build_code_review_report(run_id, final_payload):
    stdout = read_text_file(final_payload.get("stdout_path") if final_payload else None)
    parsed = None
    try:
        candidate = json.loads(stdout or "{}")
        if isinstance(candidate, dict):
            parsed = candidate
    except json.JSONDecodeError:
        parsed = None
    findings = parsed.get("findings") if parsed else []
    if not isinstance(findings, list):
        findings = []
    summary = parsed.get("summary") if parsed else None
    next_steps = parsed.get("next_steps") if parsed else None
    if not isinstance(next_steps, list):
        next_steps = []
    return {
        "schema_version": 1,
        "kind": "code-review",
        "run_id": run_id,
        "summary": summary or "Code review completed. Structured findings were not emitted by the provider.",
        "findings": [finding for finding in findings if isinstance(finding, dict)],
        "next_steps": [str(step) for step in next_steps],
        "artifacts": {
            "transcript_path": final_payload.get("transcript_path") if final_payload else None,
            "stdout_path": final_payload.get("stdout_path") if final_payload else None,
            "stderr_path": final_payload.get("stderr_path") if final_payload else None,
        },
    }
