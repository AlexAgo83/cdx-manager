import json
import os
import tempfile
from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def registry_path(base_dir):
    return os.path.join(base_dir, "runs.json")


def _read_registry(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
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
        "pid": None,
        "started_at": utc_now_iso(),
        "ended_at": None,
        "duration_seconds": None,
        "exit_code": None,
        "usage": None,
        "artifacts": dict(artifacts or {}),
        "error": None,
        "task_report": None,
        "final_payload": None,
    }


class RunRegistry:
    def __init__(self, base_dir):
        self.path = registry_path(base_dir)

    def start(self, run_id, *, kind, session, provider, model, cwd, artifacts=None):
        data = _read_registry(self.path)
        data["runs"] = [run for run in data["runs"] if run.get("run_id") != run_id]
        record = _base_record(run_id, kind=kind, session=session, provider=provider, model=model, cwd=cwd, artifacts=artifacts)
        data["runs"].insert(0, record)
        _write_registry(self.path, data)
        return record

    def finish(self, run_id, *, status, final_payload=None, run_info=None, error=None, task_report=None):
        data = _read_registry(self.path)
        now = utc_now_iso()
        for run in data["runs"]:
            if run.get("run_id") != run_id:
                continue
            run["status"] = status
            run["ended_at"] = now
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

    def list(self, limit=20):
        data = _read_registry(self.path)
        changed = _refresh_stale_runs(data)
        if changed:
            _write_registry(self.path, data)
        return data["runs"][: max(0, int(limit or 20))]

    def get(self, run_id):
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
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
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
