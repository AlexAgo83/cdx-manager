"""Best-effort usage readers for interactive provider sessions."""

import json
import os
import time

from .run_usage import claude_usage_dedup_key, normalize_usage

MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024
MAX_TRANSCRIPT_CANDIDATES = 1000
MAX_TRANSCRIPT_SCAN_SECONDS = 1

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
    deadline = time.monotonic() + MAX_TRANSCRIPT_SCAN_SECONDS
    for directory, subdirs, names in os.walk(root):
        if time.monotonic() >= deadline:
            return max(candidates, default=(None, None))[1]
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
                    return max(candidates)[1]
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
            if not isinstance(usage, dict) or not usage:
                continue
            # Codex counts cached tokens inside `input_tokens`; reduce to the
            # uncached remainder so the field means what run_usage says it
            # means. Same subset check as the headless reader: a cached count
            # larger than the input count is not a subset, so that record is
            # left alone rather than forced to zero.
            reported_input = _number(usage.get("input_tokens"))
            cache_read = _number(usage.get("cached_input_tokens"))
            latest = normalize_usage(
                input_tokens=reported_input - cache_read if cache_read <= reported_input else reported_input,
                cache_read_tokens=cache_read,
                output_tokens=_number(usage.get("output_tokens")),
                reasoning_tokens=_number(usage.get("reasoning_output_tokens")) or None,
            )
        except (TypeError, ValueError):
            continue
    return latest


def _claude_usage(handle):
    """Sum Claude's per-message usage across the transcript.

    Cache creation and cache read are kept apart rather than summed on the way
    in: they cost 1.25x and 0.1x of uncached input, so fusing them here would
    destroy the only information a cost-aware figure needs. Claude reports no
    separate reasoning count -- thinking is billed as output and is already
    inside `output_tokens` -- so that field stays absent by design.
    """
    totals = {"input_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0}
    seen = set()
    for line in handle:
        try:
            record = json.loads(line)
            message = record.get("message") or {}
            usage = message.get("usage") or {}
            if record.get("type") != "assistant" or not usage:
                continue
            identifier = claude_usage_dedup_key(record)
            if identifier is not None:
                if identifier in seen:
                    continue
                seen.add(identifier)
            totals["input_tokens"] += _number(usage.get("input_tokens"))
            totals["cache_creation_tokens"] += _number(usage.get("cache_creation_input_tokens"))
            totals["cache_read_tokens"] += _number(usage.get("cache_read_input_tokens"))
            totals["output_tokens"] += _number(usage.get("output_tokens"))
        except (TypeError, ValueError):
            continue
    if not seen and not any(totals.values()):
        return None
    return normalize_usage(**totals)


def _number(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
