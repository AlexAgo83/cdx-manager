import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from .errors import CdxError
from .fs_utils import atomic_write
from .run_usage import _parse_json_records, coerce_usage
from .session_helpers import _process_is_running


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def registry_path(base_dir):
    return os.path.join(base_dir, "runs.json")


# A waiter waits. `fcntl.flock` blocks until the lock is free, but Windows'
# `LK_LOCK` retries ten times at one-second intervals and then raises
# EDEADLOCK, so the same contention produced a wait on one platform and an
# OSError on the other. Twenty parallel runs writing this registry is the load
# cdx exists to carry, and on a physical Windows machine it exhausted that
# budget - CI never showed it, being less contended than a real desktop.
REGISTRY_LOCK_TIMEOUT_SECONDS = 120
_LOCK_RETRY_SECONDS = 0.05


def _acquire_windows_lock(handle, timeout_seconds, label="run registry"):
    """Block until the byte is locked, or give up with a nameable error.

    Uses the non-blocking form and does the waiting here, so the wait is
    bounded by a deadline cdx chooses rather than by `LK_LOCK`'s fixed ten
    attempts. Unbounded would be worse than the original: a stuck holder would
    hang every later command with nothing to report.
    """
    import msvcrt

    deadline = time.monotonic() + timeout_seconds
    while True:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise CdxError(
                    f"Timed out waiting for the {label} lock after "
                    f"{timeout_seconds}s. Another cdx process may be stuck holding it.",
                    75,
                ) from None
            time.sleep(_LOCK_RETRY_SECONDS)


def _acquire_posix_lock(handle, timeout_seconds, label="run registry"):
    """Acquire a POSIX advisory lock within the same bounded wait as Windows."""
    import fcntl

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise CdxError(
                    f"Timed out waiting for the {label} lock after "
                    f"{timeout_seconds}s. Another cdx process may be stuck holding it.",
                    75,
                ) from None
            time.sleep(_LOCK_RETRY_SECONDS)


@contextmanager
def _registry_lock(path, timeout_seconds=REGISTRY_LOCK_TIMEOUT_SECONDS, label="run registry"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "a") as handle:
        if sys.platform == "win32":
            import msvcrt
            _acquire_windows_lock(handle, timeout_seconds, label)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            _acquire_posix_lock(handle, timeout_seconds, label)
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
    atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n", mode=0o600)


def _is_pid_alive(pid):
    return _process_is_running(pid)


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
        if run.get("background_path") == "provider_native":
            # The provider owns this agent's lifecycle and the pid it reports
            # belongs to a daemon helper, not the run. Sweeping on pid liveness
            # would mark a healthy delegated run stale; its terminal status
            # comes from the provider instead.
            continue
        pid = run.get("pid")
        if pid and _is_pid_alive(pid):
            continue
        run["status"] = "stale"
        run["ended_at"] = now
        run["error"] = {"code": "stale_process", "message": "Run was marked running but no live provider process was found."}
        changed = True
    return changed


# Every update rewrites the whole registry under the lock, so it must not grow
# with every run ever made. Running runs are always kept; runs are newest first.
MAX_FINISHED_RUNS = 500


def _prune_finished_runs(data):
    kept, finished = [], 0
    for run in data["runs"]:
        if run.get("status") != "running":
            finished += 1
            if finished > MAX_FINISHED_RUNS:
                continue
        kept.append(run)
    data["runs"] = kept


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
        # Two handles, because the provider uses two: the session id names the
        # transcript file, the short agent id is what `claude stop` accepts.
        "provider_session_id": None,
        "provider_agent_id": None,
        "error": None,
        "task_report": None,
        "final_payload": None,
    }


def _check_capacity(data, max_parallel):
    _refresh_stale_runs(data)
    running = sum(1 for run in data["runs"] if run.get("status") == "running")
    if running >= max_parallel:
        raise CdxError(
            f"{running} run(s) already running, the limit is {max_parallel}. "
            "Wait for one to finish (cdx runs --json) or raise --max-parallel.",
            code="too_many_runs",
        )


class RunRegistry:
    def __init__(self, base_dir):
        self.path = registry_path(base_dir)

    def check_capacity(self, max_parallel):
        """Raise too_many_runs now, before a refused run changes any session state.

        `start()` checks again under the same lock, so a run that slips in
        between is still refused there.
        """
        with _registry_lock(self.path):
            _check_capacity(_read_registry(self.path), max_parallel)

    def start(self, run_id, *, kind, session, provider, model, cwd, artifacts=None, label=None, max_parallel=None,
              parent_run_id=None, conversation_id=None, launch=None, reasoning_effort=None, project=None, project_source="unknown"):
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            data["runs"] = [run for run in data["runs"] if run.get("run_id") != run_id]
            if max_parallel:
                # Counted under the lock and without this run's own record, which a
                # detached child writes a second time under the same id.
                _check_capacity(data, max_parallel)
            record = _base_record(run_id, kind=kind, session=session, provider=provider, model=model, cwd=cwd, artifacts=artifacts)
            record.update(parent_run_id=parent_run_id, conversation_id=conversation_id,
                          launch=dict(launch or {}), reasoning_effort=reasoning_effort,
                          project=project, project_source=project_source)
            if label:
                record["label"] = label
            data["runs"].insert(0, record)
            _prune_finished_runs(data)
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

    def record_attempt(self, run_id, artifacts):
        """Keep live tail paths on this supervisor's current attempt."""
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            for run in data["runs"]:
                if run.get("run_id") == run_id and run.get("status") == "running":
                    run["attempt_id"] = artifacts.get("attempt_id")
                    run["artifacts"] = {key: artifacts.get(key) for key in ("transcript_path", "stdout_path", "stderr_path")}
                    _write_registry(self.path, data)
                    return run
        return None

    def record_background(self, run_id, *, path, provider_session_id=None, provider_agent_id=None):
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            for run in data["runs"]:
                if run.get("run_id") != run_id:
                    continue
                run["background_path"] = path
                run["provider_session_id"] = provider_session_id
                if provider_session_id:
                    run["conversation_id"] = provider_session_id
                run["provider_agent_id"] = provider_agent_id
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

    def record_recovery(self, run_id, event):
        """Publish retries and fallbacks while a supervised run is still active."""
        with _registry_lock(self.path):
            data = _read_registry(self.path)
            for run in data["runs"]:
                if run.get("run_id") == run_id:
                    run.setdefault("recovery_events", []).append({"at": utc_now_iso(), **event})
                    _write_registry(self.path, data)
                    return

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
                if run_info.get("launch"):
                    run["launch"] = run_info["launch"]
                run["exit_code"] = run_info.get("returncode")
                run["artifacts"] = {
                    **(run.get("artifacts") or {}),
                    "transcript_path": run_info.get("transcript_path"),
                    "stdout_path": run_info.get("stdout_path"),
                    "stderr_path": run_info.get("stderr_path"),
                }
            if final_payload:
                # Normalize on the way in, not on the way out: this record is
                # what `cdx run-status` and `cdx run-report` publish, and it
                # used to store whichever shape the producing reader emitted.
                run["usage"] = coerce_usage(final_payload.get("usage"), provider=run.get("provider"))
                run["usage_model"] = final_payload.get("usage_model")
                for key in ("usage_evidence", "usage_models", "attempt_id", "attempts", "cost_usd", "cost_status", "cost_reason", "budget_status"):
                    run[key] = final_payload.get(key)
                run["conversation_id"] = final_payload.get("conversation_id") or run.get("conversation_id")
                run["parent_run_id"] = final_payload.get("parent_run_id") or run.get("parent_run_id")
                if "reasoning_effort" in final_payload:
                    run["reasoning_effort"] = final_payload["reasoning_effort"]
                run["model"] = final_payload.get("model")
                run["final_payload"] = final_payload
            if error:
                run["error"] = error
            if task_report:
                run["task_report"] = task_report
            _write_registry(self.path, data)
            return run
        return None

    def list(self, limit=20, since=None, running=False):
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
        if running:
            # Every in-flight run, uncapped: a caller counting live runs against
            # a cap must not be handed a truncated count.
            return [run for run in runs if run.get("status") == "running"]
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


def _record_final_message(record):
    """The final assistant text one provider record carries, or None."""
    if not isinstance(record, dict):
        return None
    # Claude: `--output-format json` ends with a `result` envelope.
    if record.get("type") == "result" and isinstance(record.get("result"), str):
        return record["result"]
    # Codex `exec --json`: an `item.completed` event wrapping an agent_message.
    item = record.get("item")
    if isinstance(item, dict) and item.get("type") == "agent_message" and isinstance(item.get("text"), str):
        return item["text"]
    # Older Codex builds wrapped it as {"msg": {"type": "agent_message", "message": ...}}.
    msg = record.get("msg")
    if isinstance(msg, dict) and msg.get("type") == "agent_message" and isinstance(msg.get("message"), str):
        return msg["message"]
    return None


def final_message(run):
    """The run's last assistant message, read the same way for every provider.

    A `--bg` run records it from the transcript as `final_payload.result`; any
    other run left it in its stdout, in the provider's own event format. None
    when neither holds one (a plain-text provider, a run that died early).
    """
    result = (run.get("final_payload") or {}).get("result")
    if isinstance(result, str) and result.strip():
        return result
    stdout_path = (run.get("artifacts") or {}).get("stdout_path")
    if not stdout_path:
        return None
    try:
        with open(stdout_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None
    if not text.strip():
        return None
    for record in reversed(_parse_json_records(text)):
        message = _record_final_message(record)
        if message is not None:
            return message
    return None


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
