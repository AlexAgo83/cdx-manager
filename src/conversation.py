"""Incremental, read-only conversation pages from provider JSONL transcripts."""

import base64
import hashlib
import json
import os
import re
from datetime import datetime

from .config import PROVIDERS
from .errors import CdxError
from .interactive_usage import conversation_transcript, resolve_transcript

MAX_LINE_BYTES = 1024 * 1024
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_CURSOR_NAMES_BYTES = 2048
REDACTED = "[REDACTED]"


def _redact(text):
    # There is no shared transcript redactor; launch argument redaction only
    # hides prompt argv. Do not read credential stores to discover secrets.
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)", REDACTED, text, flags=re.S)
    text = re.sub(r"(?i)\b(?:[\w.-]*(?:password|passwd|secret|api[_-]?key|token)|authorization)\b[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)", REDACTED, text)
    text = re.sub(r"(?i)\b(?:bearer|basic)\s+[a-z0-9._~+/=-]+", REDACTED, text)
    text = re.sub(r"\b(?:sk-[a-zA-Z0-9_-]+|gh[pousr]_[a-zA-Z0-9]+|github_pat_[a-zA-Z0-9_]+|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}|xox[baprs]-[a-zA-Z0-9-]+|AIza[a-zA-Z0-9_-]+)\b", REDACTED, text)
    text = re.sub(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b", REDACTED, text)
    text = re.sub(r"https?://(?:hooks\.slack\.com/services|(?:discord(?:app)?\.com)/api/webhooks)/[^\s\"'<>]+", REDACTED, text)
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)


def _entry(role, text="", name=None, summary=None, at=None):
    return {"role": role, "text": _redact(text), "tool_name": _redact(name) if name else None,
            "tool_summary": summary, "at": at, "id": None}


def _tool_name(message, names, result=False):
    identifier = message.get("call_id") or message.get("tool_use_id") or message.get("id")
    key = hashlib.sha256(identifier.encode()).hexdigest() if isinstance(identifier, str) else None
    name = message.get("name") or (names.get(key) if result else None)
    name = _redact(name) if isinstance(name, str) else "tool"
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.:/-]{0,99}", name):
        name = "tool"
    if key and not result:
        if len(names) >= 100:
            names.pop(next(iter(names)))
        names[key] = name
    return name


def _entries(provider, record, names):
    if not isinstance(record, dict):
        return []
    stamp = record.get("timestamp")
    try:
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        stamp = None
    if provider == "codex":
        # event_msg repeats response_item messages; consume only canonical items.
        if record.get("type") != "response_item":
            return []
        message = record.get("payload")
    else:
        message = record.get("message")
    if not isinstance(message, dict):
        return []
    kind = message.get("type")
    if isinstance(kind, str) and (kind.endswith("_call") or kind.endswith("_call_output")):
        result = kind.endswith("output")
        tool = message
        if not message.get("name") and kind not in ("function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"):
            tool = {**message, "name": kind.removesuffix("_output").removesuffix("_call")}
        name = _tool_name(tool, names, result)
        return [_entry("tool", name=name, summary="Result recorded" if result else "Call recorded", at=stamp)]
    role = message.get("role") or record.get("type")
    if role not in ("user", "assistant", "tool"):
        return []
    if role == "tool":
        return [_entry("tool", name=_tool_name(message, names, True), summary="Result recorded", at=stamp)]
    content = message.get("content")
    if isinstance(content, str):
        return [_entry(role, content, at=stamp)]
    if not isinstance(content, list):
        return []
    entries = []
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind in ("text", "input_text", "output_text") and isinstance(block.get("text"), str):
            entries.append(_entry(role, block["text"], at=stamp))
        elif kind in ("tool_use", "tool_result"):
            name = _tool_name(block, names, kind == "tool_result")
            entries.append(_entry("tool", name=name, summary="Call recorded" if kind == "tool_use" else "Result recorded", at=stamp))
    return entries


def _anchor(handle, offset):
    handle.seek(max(0, offset - 128))
    return hashlib.sha256(handle.read(min(offset, 128))).hexdigest()


def _field_start(prefix, field, start=0):
    """Find an object field before any incomplete value in a bounded prefix."""
    decoder = json.JSONDecoder()
    whitespace = re.compile(r"\s*")
    try:
        start = whitespace.match(prefix, start).end()
        if prefix[start] != "{":
            return None
        start += 1
        while True:
            start = whitespace.match(prefix, start).end()
            key, end = decoder.raw_decode(prefix, start)
            if not isinstance(key, str):
                return None
            end = whitespace.match(prefix, end).end()
            if prefix[end] != ":":
                return None
            start = whitespace.match(prefix, end + 1).end()
            if key == field:
                return start
            _, end = decoder.raw_decode(prefix, start)
            end = whitespace.match(prefix, end).end()
            if prefix[end] != ",":
                return None
            start = end + 1
    except (ValueError, IndexError, RecursionError):
        return None


def _oversized_entry(provider, prefix):
    prefix = prefix.decode("utf-8", errors="replace")
    message = _field_start(prefix, "payload" if provider == "codex" else "message")
    role = _field_start(prefix, "role", message) if message is not None else None
    if role is None and provider != "codex":
        role = _field_start(prefix, "type")
    try:
        value, _ = json.JSONDecoder().raw_decode(prefix, role) if role is not None else (None, 0)
    except (ValueError, RecursionError):
        value = None
    return _entry(value if value in ("user", "assistant", "tool") else "tool",
                  "[élément trop volumineux ignoré]")


def read_conversation(provider, auth_home=None, *, conversation_id=None, started_at=None,
                      terminal_transcript=None, cursor=None, limit=100, fallback_to_recency=False):
    """Return a JSON-serializable page; pass next_cursor back unchanged to poll.

    Entries follow file/block order. Cursors bind a byte offset and block index
    to the resolved file; reset_required means discard the old cursor and page
    again from the beginning. Incomplete trailing lines are retried next time.
    Only implicit session identities may opt into fallback_to_recency.
    Tool bodies and reasoning blocks are never returned. Ollama PTY captures
    cannot reliably distinguish roles and are explicitly unsupported.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise CdxError("Conversation limit must be an integer between 1 and 1000.")
    page = {"status": "ok", "reason": None, "provider": provider, "entries": [], "next_cursor": None, "has_more": False,
            "resolution_method": None}
    if provider not in PROVIDERS or provider == "ollama":
        return {**page, "status": "unsupported", "reason": "no_structured_transcript_reader"}
    # An explicit conversation must never fall back to an unrelated recent file.
    if conversation_id:
        path = conversation_transcript(provider, auth_home, conversation_id)
        if path:
            page["resolution_method"] = "conversation_id"
        elif fallback_to_recency:
            path, page["resolution_method"] = resolve_transcript(provider, auth_home)
    else:
        path, page["resolution_method"] = resolve_transcript(provider, auth_home, started_at, terminal_transcript=terminal_transcript)
    if not path:
        return {**page, "status": "unavailable", "reason": "transcript_not_found"}
    try:
        with open(path, "rb") as handle:
            stat = os.fstat(handle.fileno())
            identity = hashlib.sha256(f"{provider}:{os.path.realpath(path)}:{stat.st_dev}:{stat.st_ino}".encode()).hexdigest()
            offset, index, names = 0, 0, {}
            if cursor is not None:
                try:
                    if not isinstance(cursor, str) or len(cursor) > 65536:
                        raise ValueError
                    state = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
                    offset, index = state["offset"], state["index"]
                    names = state["names"]
                    if (not isinstance(names, dict) or len(names) > 100
                            or any(not isinstance(k, str) or not re.fullmatch(r"[0-9a-f]{64}", k)
                                   or not isinstance(v, str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.:/-]{0,99}", v)
                                   or _redact(v) != v for k, v in names.items())):
                        raise ValueError
                    if (state["v"] != 1 or state["file"] != identity
                            or type(offset) is not int or type(index) is not int
                            or not 0 <= offset <= stat.st_size or not 0 <= index <= MAX_LINE_BYTES
                            or state["anchor"] != _anchor(handle, offset)):
                        raise ValueError
                except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
                    return {**page, "status": "reset_required", "reason": "invalid_or_stale_cursor"}
            handle.seek(offset)
            scanned = 0
            while len(page["entries"]) < limit and scanned < MAX_PAGE_BYTES:
                start = handle.tell()
                line = handle.readline(MAX_LINE_BYTES + 1)
                if len(line) > MAX_LINE_BYTES:
                    entry = _oversized_entry(provider, line)
                    # Finish this record even beyond the page scan budget. Never
                    # retain its body, and retry from start if its newline is pending.
                    while line and not line.endswith(b"\n"):
                        line = handle.readline(MAX_LINE_BYTES + 1)
                    if not line:
                        break
                    entries = [entry]
                else:
                    if not line or not line.endswith(b"\n"):
                        break
                    try:
                        entries = _entries(provider, json.loads(line), names)
                    except (ValueError, UnicodeError):
                        entries = []
                scanned += handle.tell() - start
                for block_index in range(index, len(entries)):
                    entry = entries[block_index]
                    entry["id"] = f"{identity[:16]}:{start}:{block_index}"
                    page["entries"].append(entry)
                    if len(page["entries"]) == limit:
                        index = block_index + 1
                        break
                else:
                    index = len(entries)
                if index < len(entries):
                    offset = start
                    break
                offset, index = handle.tell(), 0
            page["has_more"] = offset < stat.st_size
            while len(json.dumps(names, separators=(",", ":")).encode()) > MAX_CURSOR_NAMES_BYTES:
                names.pop(next(iter(names)))
            state = {"v": 1, "file": identity, "offset": offset, "index": index, "anchor": _anchor(handle, offset), "names": names}
            page["next_cursor"] = base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()
            return page
    except OSError:
        return {**page, "status": "unavailable", "reason": "transcript_unreadable", "entries": []}
