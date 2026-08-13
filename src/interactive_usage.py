"""Best-effort usage readers for interactive provider sessions."""

import json
import os

MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024
MAX_TRANSCRIPT_CANDIDATES = 1000

def extract_interactive_usage(provider, auth_home, started_at=None):
    """Return the newest provider-native usage after an interactive session.

    Provider transcripts are not stable public APIs.  A missing or changed
    record is therefore ordinary absence, never a launch failure.
    """
    path = _latest_transcript(provider, auth_home, started_at)
    if not path:
        return None, None
    try:
        if os.path.getsize(path) > MAX_TRANSCRIPT_BYTES:
            return None, path
        with open(path, encoding="utf-8", errors="replace") as handle:
            return (_codex_usage(handle) if provider == "codex" else _claude_usage(handle)), path
    except OSError:
        return None, path


def _latest_transcript(provider, auth_home, started_at):
    if not auth_home:
        return None
    root = os.path.join(auth_home, "sessions") if provider == "codex" else os.path.join(auth_home, ".claude", "projects")
    if not os.path.isdir(root):
        return None
    cutoff = _timestamp(started_at)
    candidates = []
    for directory, subdirs, names in os.walk(root):
        if provider == "claude":
            subdirs[:] = [name for name in subdirs if name != "subagents"]
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(directory, name)
            try:
                modified = os.path.getmtime(path)
            except OSError:
                continue
            if cutoff is None or modified >= cutoff:
                candidates.append((modified, path))
                if len(candidates) > MAX_TRANSCRIPT_CANDIDATES:
                    return None
    return max(candidates, default=(None, None))[1]


def _timestamp(value):
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _codex_usage(handle):
    latest = None
    for line in handle:
        try:
            record = json.loads(line)
            payload = record.get("payload") or {}
            usage = ((payload.get("info") or {}).get("total_token_usage") or {}) if payload.get("type") == "token_count" else {}
            candidate = _normalize(usage, cached_key="cached_input_tokens", reasoning_key="reasoning_output_tokens")
            if candidate:
                latest = candidate
        except (TypeError, ValueError):
            continue
    return latest


def _claude_usage(handle):
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    seen = set()
    for line in handle:
        try:
            record = json.loads(line)
            message = record.get("message") or {}
            usage = message.get("usage") or {}
            identifier = record.get("uuid")
            if record.get("type") != "assistant" or not usage or (identifier and identifier in seen):
                continue
            if identifier:
                seen.add(identifier)
            totals["input_tokens"] += _number(usage.get("input_tokens"))
            totals["cached_input_tokens"] += _number(usage.get("cache_creation_input_tokens")) + _number(usage.get("cache_read_input_tokens"))
            totals["output_tokens"] += _number(usage.get("output_tokens"))
        except (TypeError, ValueError):
            continue
    if not seen and not any(totals.values()):
        return None
    totals["reasoning_tokens"] = None
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    return totals


def _normalize(usage, cached_key, reasoning_key):
    if not isinstance(usage, dict) or not usage:
        return None
    return {
        "input_tokens": _number(usage.get("input_tokens")),
        "cached_input_tokens": _number(usage.get(cached_key)),
        "output_tokens": _number(usage.get("output_tokens")),
        "reasoning_tokens": _number(usage.get(reasoning_key)) or None,
        "total_tokens": _number(usage.get("total_tokens")) or None,
    }


def _number(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
