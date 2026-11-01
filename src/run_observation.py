"""Supervisor-owned, content-free snapshots of isolated provider observations."""

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from .run_usage import _usage_from_dict, extract_run_conversation_id, extract_run_usage


def _open_rollout(root, path):
    """Walk relative to the pinned attempt directory without following symlinks."""
    parts = Path(path).relative_to(root).parts
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)


def codex_attempt_evidence(auth_home, stdout_path, started_at):
    """Read only the exact thread in a fresh attempt's volatile sessions mount.

    Do not import claimed costs, requested models, messages, or arbitrary files
    from the workspace. The exported object is never writable by the sandbox.
    """
    from .history_models import _exact_transcript
    from .interactive_usage import MAX_TRANSCRIPT_BYTES

    usage = extract_run_usage("codex", stdout_path)
    identifier = extract_run_conversation_id("codex", stdout_path)
    evidence = {"source": "isolated_codex_rollout", "stdout_path": str(stdout_path),
                "thread_id": identifier, "started_at": started_at, "models": [],
                "turns": [], "usage": usage}
    if not identifier:
        return evidence
    path, error = _exact_transcript("codex", auth_home, identifier)
    if error or not path:
        return evidence
    return codex_rollout_evidence(auth_home, path, evidence, MAX_TRANSCRIPT_BYTES)


def codex_rollout_evidence(auth_home, path, evidence, max_bytes):
    """Validate exact-attempt rollout evidence identically on local and remote hosts."""
    usage = evidence["usage"]
    identifier = evidence["thread_id"]
    started_at = evidence["started_at"]
    models = set()
    turns = []
    identity = False
    complete_models = True
    counters = None
    ended_at = datetime.now(timezone.utc)
    try:
        descriptor = _open_rollout(auth_home, path)
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return evidence
            text = handle.read(max_bytes + 1)
        if len(text) > max_bytes:
            return evidence
        for line in text.splitlines():
            record = json.loads(line)
            payload = record.get("payload") or {}
            if record.get("type") == "session_meta":
                if payload.get("id") != identifier:
                    return evidence
                identity = True
            if record.get("type") == "event_msg" and payload.get("type") == "token_count":
                counters = _usage_from_dict((payload.get("info") or {}).get("total_token_usage") or {}, provider="codex")
            if record.get("type") != "turn_context":
                continue
            timestamp = record.get("timestamp")
            if (not timestamp or datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    < datetime.fromisoformat(started_at.replace("Z", "+00:00"))):
                complete_models = False
                continue
            if datetime.fromisoformat(timestamp.replace("Z", "+00:00")) > ended_at:
                complete_models = False
                continue
            model = payload.get("model")
            if not isinstance(model, str) or not model:
                complete_models = False
                continue
            models.add(model)
            turn_id = payload.get("turn_id")
            turns.append({"turn_id": turn_id if isinstance(turn_id, str) else None, "timestamp": timestamp, "model": model})
    except (OSError, ValueError, TypeError, AttributeError):
        return evidence
    # Rollout counters must corroborate exec's measured counters. A free-form
    # model/cost claim or a previous conversation's context is insufficient.
    matches = counters is not None and all(value is None or counters.get(key) == value for key, value in usage.items())
    if identity and matches:
        evidence.update(models=sorted(models) if complete_models else [], turns=turns, ended_at=ended_at.isoformat())
        if usage.get("total_tokens") is None:
            evidence["measurement_usage"] = counters
    return evidence
