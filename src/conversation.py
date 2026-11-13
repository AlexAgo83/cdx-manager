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


# Codex injects instructions and turn context as user-role messages; these
# prefixes mirror its contextual-user-message markers.
_CODEX_CONTEXT_PREFIXES = (
    "# AGENTS.md instructions", "<user_instructions>", "<environment_context>", "<skill>",
    "<turn_aborted>", "<subagent_notification>",
)


def _conversation_record(provider, kind):
    # Provider bookkeeping can carry the same text as real conversation records.
    # Claude Code records messages typed while the agent works as queued_command attachments.
    return kind == "response_item" if provider == "codex" else kind in ("user", "assistant", "attachment")


def _queued_prompt(record):
    attachment = record.get("attachment")
    if not isinstance(attachment, dict) or attachment.get("type") != "queued_command":
        return None
    # Print mode (cdx remote control) records an operator prompt without an origin.
    origin = attachment.get("origin")
    if (origin or {}).get("kind") != "human" and not (origin is None and attachment.get("commandMode") == "prompt"):
        return None
    return attachment.get("prompt")


_CLAUDE_HARNESS = re.compile(
    r"\s*(?:<(?P<tag>task-notification|local-command-stdout|local-command-stderr|command-name|command-message|command-args|system-reminder)>"
    r"(?:(?!</(?P=tag)>).)*</(?P=tag)>\s*)+", re.S,
)
# Claude Code wraps long pasted text in matching tags; show only the pasted text.
_CLAUDE_PASTED = re.compile(r'<pasted_content id="([0-9A-Za-z]{1,32})">\n?(.*?)\n?</pasted_content id="\1">', re.S)
_CLAUDE_MID_TURN_START = "The user sent a new message while you were working:\n"
_CLAUDE_MID_TURN_END = re.compile(
    r"\n+This is how Claude Code surfaces messages the user sends mid-turn[^\n]*"
    r"Address the message above as you continue this turn\.\s*\Z"
)


def _claude_user_content(content):
    """Remove complete harness wrappers, preserving ordinary prose and images."""
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
    if not isinstance(blocks, list):
        return content
    blocks = [dict(block) if isinstance(block, dict) else block for block in blocks]
    texts = [block for block in blocks if isinstance(block, dict)
             and block.get("type") == "text" and isinstance(block.get("text"), str)]
    for block in texts:
        block["text"] = _CLAUDE_PASTED.sub(r"\2", block["text"])
    # Require both anchored boundaries; a quoted sentence alone is user content.
    if texts and texts[0]["text"].startswith(_CLAUDE_MID_TURN_START):
        end = _CLAUDE_MID_TURN_END.search(texts[-1]["text"])
        if end:
            texts[-1]["text"] = texts[-1]["text"][:end.start()]
            texts[0]["text"] = texts[0]["text"][len(_CLAUDE_MID_TURN_START):].strip("\n")
    return [block for block in blocks if not (
        isinstance(block, dict) and block.get("type") == "text"
        and isinstance(block.get("text"), str)
        and (not block["text"].strip() or _CLAUDE_HARNESS.fullmatch(block["text"]))
    )]


def _entries(provider, record, names):
    if not isinstance(record, dict):
        return []
    if not _conversation_record(provider, record.get("type")):
        return []
    # Claude Code marks its own user-role notes (image size hints, caveats) as isMeta.
    if provider == "claude" and record.get("isMeta"):
        return []
    stamp = record.get("timestamp")
    try:
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        stamp = None
    if provider == "codex":
        message = record.get("payload")
    elif record.get("type") == "attachment":
        prompt = _queued_prompt(record)
        message = {"role": "user", "content": prompt} if isinstance(prompt, (str, list)) else None
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
    if provider == "claude" and role == "user":
        content = _claude_user_content(content)
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
            if provider == "codex" and role == "user" and block["text"].lstrip().startswith(_CODEX_CONTEXT_PREFIXES):
                continue
            entries.append(_entry(role, block["text"], at=stamp))
        elif kind in ("tool_use", "tool_result"):
            name = _tool_name(block, names, kind == "tool_result")
            entries.append(_entry("tool", name=name, summary="Call recorded" if kind == "tool_use" else "Result recorded", at=stamp))
    if provider == "claude" and role == "user" and not any(e["role"] == "user" for e in entries):
        if any(isinstance(block, dict) and block.get("type") == "image" for block in content):
            entries.append(_entry("user", at=stamp))
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
    kind = _field_start(prefix, "type")
    try:
        value, _ = json.JSONDecoder().raw_decode(prefix, kind) if kind is not None else (None, 0)
    except (ValueError, RecursionError):
        value = None
    if not _conversation_record(provider, value):
        return None
    if value == "attachment":
        # An oversized queued message carries a pasted image; keep its leading text when readable.
        attachment = _field_start(prefix, "attachment")
        if attachment is None or '"queued_command"' not in prefix[attachment:attachment + 200]:
            return None
        text = _field_start(prefix, "text", prefix.find("{", prefix.find('"prompt"', attachment)))
        try:
            text, _ = json.JSONDecoder().raw_decode(prefix, text) if text is not None else ("", 0)
        except (ValueError, RecursionError):
            text = ""
        blocks = _claude_user_content([{"type": "text", "text": text}]) if isinstance(text, str) else []
        return _entry("user", blocks[0]["text"] if blocks else "")
    message = _field_start(prefix, "payload" if provider == "codex" else "message")
    if message is None or prefix[message:message + 1] != "{":
        return None
    role = _field_start(prefix, "role", message)
    if role is None and provider != "codex":
        role = _field_start(prefix, "type")
    try:
        value, _ = json.JSONDecoder().raw_decode(prefix, role) if role is not None else (None, 0)
    except (ValueError, RecursionError):
        value = None
    if provider == "claude" and value == "user":
        # A large tool result (an image read) is tool output, never an operator message.
        content = _field_start(prefix, "content", message)
        if content is not None and '"tool_result"' in prefix[content:content + 300]:
            return _entry("tool", name="tool", summary="Result recorded")
    return _entry(value if value in ("user", "assistant", "tool") else "tool",
                  "[élément trop volumineux ignoré]")


REVERSE_BLOCK_BYTES = 64 * 1024


def _encode_cursor(handle, identity, offset, index, names):
    names = dict(names)
    while len(json.dumps(names, separators=(",", ":")).encode()) > MAX_CURSOR_NAMES_BYTES:
        names.pop(next(iter(names)))
    state = {"v": 1, "file": identity, "offset": offset, "index": index,
             "anchor": _anchor(handle, offset), "names": names}
    return base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()


def _reverse_records(handle, end):
    """Yield line positions and bounded prefixes, including an incomplete tail."""
    position, line_end, length, prefix = end, end, 0, b""
    while position:
        start = max(0, position - REVERSE_BLOCK_BYTES)
        handle.seek(start)
        block = handle.read(position - start)
        right = len(block)
        while right:
            newline = block.rfind(b"\n", 0, right)
            left = newline + 1
            part = block[left:right]
            length += len(part)
            prefix = (part + prefix)[:MAX_LINE_BYTES + 1]
            if newline < 0:
                break
            if length:
                yield start + left, line_end, prefix, length
            line_end = start + left
            length, prefix, right = 1, b"\n", newline
        position = start
    if length:
        yield 0, line_end, prefix, length


def _record_entries(provider, prefix, length, names):
    if length > MAX_LINE_BYTES:
        entry = _oversized_entry(provider, prefix)
        return [entry] if entry is not None else []
    try:
        return _entries(provider, json.loads(prefix), names)
    except (ValueError, UnicodeError, RecursionError):
        return []


class _NameLookups(dict):
    def __init__(self):
        super().__init__()
        self.missing = set()

    def get(self, key, default=None):
        if key not in self:
            self.missing.add(key)
        return super().get(key, default)


def _read_tail(handle, stat, identity, provider, page, count, before):
    end, stop_index = stat.st_size, None
    snapshot = {"size": stat.st_size, "mtime": stat.st_mtime_ns,
                "anchor": _anchor(handle, stat.st_size)}
    if before is not None:
        try:
            if not isinstance(before, str) or len(before) > 4096:
                raise ValueError
            state = json.loads(base64.urlsafe_b64decode(before.encode("ascii")))
            end, stop_index = state["offset"], state["index"]
            snapshot = state["snapshot"]
            size = snapshot["size"]
            if (state["v"] != 2 or state["file"] != identity or state["direction"] != "before"
                    or type(end) is not int or type(stop_index) is not int
                    or type(size) is not int or not 0 <= end <= size <= stat.st_size
                    or not 0 <= stop_index <= MAX_LINE_BYTES
                    or state["anchor"] != _anchor(handle, end)
                    or snapshot["anchor"] != _anchor(handle, size)
                    or (size == stat.st_size and snapshot["mtime"] != stat.st_mtime_ns)):
                raise ValueError
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
            return {**page, "status": "reset_required", "reason": "invalid_or_stale_cursor"}
    # Include the boundary record when a page split its content blocks.
    boundary_end = end
    if stop_index:
        handle.seek(end)
        line = handle.readline(MAX_LINE_BYTES + 1)
        if not line.endswith(b"\n") or len(line) > MAX_LINE_BYTES:
            return {**page, "status": "reset_required", "reason": "invalid_or_stale_cursor"}
        boundary_end = end + len(line)
    selected, remaining, names = [], count, {}
    earliest = (end, stop_index or 0)
    forward_end = (end, stop_index or 0)
    lookback_start = None
    missing_names = set()
    for start, record_end, prefix, length in _reverse_records(handle, boundary_end):
        if not prefix.endswith(b"\n") and length <= MAX_LINE_BYTES:
            # The first reverse record may be an unfinished provider write.
            forward_end = (start, 0)
            continue
        if length > MAX_LINE_BYTES:
            handle.seek(record_end - 1)
            if handle.read(1) != b"\n":
                forward_end = (start, 0)
                continue
        local_names = _NameLookups()
        entries = _record_entries(provider, prefix, length, local_names)
        if start == end and stop_index and stop_index >= len(entries):
            return {**page, "status": "reset_required", "reason": "invalid_or_stale_cursor"}
        if remaining:
            upper = stop_index if start == end and stop_index is not None else len(entries)
            lower = max(0, upper - remaining)
            if upper > lower:
                selected.append((start, prefix, length, lower, upper))
                missing_names.update(local_names.missing)
                missing_names.difference_update(local_names)
                remaining -= upper - lower
                earliest = (start, lower)
                if len(selected) == 1:
                    forward_end = (start, upper) if upper < len(entries) else (record_end, 0)
            if not remaining:
                lookback_start = start
        else:
            # Recover recent call names before normalizing the selected window.
            for key, name in local_names.items():
                names.setdefault(key, name)
            missing_names.difference_update(local_names)
            budget = MAX_PAGE_BYTES if missing_names else REVERSE_BLOCK_BYTES
            if len(names) >= 100 or lookback_start - start >= budget:
                break
    if remaining:
        earliest = (0, 0)
    names = dict(reversed(list(names.items())))
    for start, prefix, length, lower, upper in reversed(selected):
        entries = _record_entries(provider, prefix, length, names)
        for index in range(lower, upper):
            entry = entries[index]
            entry["id"] = f"{identity[:16]}:{start}:{index}"
            page["entries"].append(entry)
    offset, index = forward_end
    page["next_cursor"] = _encode_cursor(handle, identity, offset, index, names)
    page["has_more"] = offset < stat.st_size
    offset, index = earliest
    page["before_cursor"] = None
    if offset or index:
        state = {"v": 2, "direction": "before", "file": identity, "offset": offset,
                 "index": index, "anchor": _anchor(handle, offset), "snapshot": snapshot}
        page["before_cursor"] = base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()
    return page


def _validate_page_options(limit, tail, cursor, before):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise CdxError("Conversation limit must be an integer between 1 and 1000.")
    if tail is not None and (type(tail) is not int or not 1 <= tail <= 1000):
        raise CdxError("Conversation tail must be an integer between 1 and 1000.")
    if cursor is not None and (tail is not None or before is not None):
        raise CdxError("Conversation --cursor cannot be combined with --tail or --before.")


def read_conversation(provider, auth_home=None, *, conversation_id=None, started_at=None,
                      terminal_transcript=None, cursor=None, limit=100, fallback_to_recency=False,
                      tail=None, before=None, cwd=None, pid=None, process_identity=None,
                      remote_endpoint=None):
    """Read a conversation page, optionally bound to a live native process.

    Process selection never uses saved session IDs or recency. Keep the returned
    opaque process_identity for later polls to detect PID reuse. Unknown evidence
    returns no entries. See docs/cli.md for platform and snapshot limitations.
    """
    _validate_page_options(limit, tail, cursor, before)
    options = dict(conversation_id=conversation_id, started_at=started_at,
                   terminal_transcript=terminal_transcript, cursor=cursor, limit=limit,
                   fallback_to_recency=fallback_to_recency, tail=tail, before=before, cwd=cwd)
    if pid is None and process_identity is None:
        return _read_conversation_page(provider, auth_home, **options)
    if conversation_id is not None or cwd is not None or started_at is not None or terminal_transcript is not None:
        raise CdxError("Process selection cannot be combined with conversation, cwd, since or terminal transcript selection.")
    from .process_conversation import resolve_process_conversation

    resolution, evidence = resolve_process_conversation(provider, auth_home, pid=pid, process_identity=process_identity,
                                                        remote_endpoint=remote_endpoint)
    page = {"status": "unavailable", "provider": provider, "entries": [], "next_cursor": None,
            "has_more": False, "resolution_scope": None, **resolution}
    if tail is not None or before is not None:
        page["before_cursor"] = None
    # Process pagination remains disabled: an unbound explicit-ID or recency
    # cursor must never cross into this mode.
    if cursor is not None or before is not None:
        return {**page, "status": "reset_required"}
    if evidence is None:
        return page
    selected = _read_conversation_page(provider, auth_home, limit=limit, tail=tail,
                                       _transcript=evidence[1], _file_identity=evidence[2])
    checked, current = resolve_process_conversation(provider, auth_home, process_identity=resolution["process_identity"],
                                                    remote_endpoint=remote_endpoint)
    if current != evidence or checked != resolution:
        return {**page, **checked, "resolution_status": "unknown", "resolution_method": None,
                "conversation_id": None, "reason": checked["reason"] or "evidence_changed"}
    if selected["status"] != "ok":
        return {**page, "resolution_status": "unknown", "resolution_method": None,
                "conversation_id": None, "reason": selected["reason"]}
    return {**selected, **resolution, "reason": None, "next_cursor": None, "before_cursor": None,
            "has_more": False}


def _read_conversation_page(provider, auth_home=None, *, conversation_id=None, started_at=None,
                      terminal_transcript=None, cursor=None, limit=100, fallback_to_recency=False, tail=None, before=None, cwd=None,
                      _transcript=None, _file_identity=None):
    """Return a JSON-serializable page; pass next_cursor back unchanged to poll.

    Entries follow file/block order. Cursors bind a byte offset and block index
    to the resolved file; reset_required means discard the old cursor and page
    again from the beginning. Incomplete trailing lines are retried next time.
    tail selects the latest entries; before selects entries preceding an opaque
    backward cursor. Both return before_cursor as well as a forward next_cursor.
    Only implicit session identities may opt into fallback_to_recency.
    Recency is restricted to cwd (the process directory by default), and to
    transcripts modified at or after started_at when supplied.
    Tool bodies and reasoning blocks are never returned. Ollama PTY captures
    cannot reliably distinguish roles and are explicitly unsupported.
    """
    _validate_page_options(limit, tail, cursor, before)
    if started_at is not None:
        try:
            datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError):
            raise CdxError("Conversation --since must be an ISO timestamp.") from None
    scope = None if _transcript is not None else {"cwd": os.path.realpath(os.path.expanduser(cwd or os.getcwd())), "since": started_at}
    page = {"status": "ok", "reason": None, "provider": provider, "entries": [], "next_cursor": None, "has_more": False,
            "resolution_method": None, "resolution_scope": None}
    if tail is not None or before is not None:
        page["before_cursor"] = None
    if provider not in PROVIDERS or provider == "ollama":
        return {**page, "status": "unsupported", "reason": "no_structured_transcript_reader"}
    # An explicit conversation must never fall back to an unrelated recent file.
    if _transcript is not None:
        path = _transcript
    elif conversation_id:
        path = conversation_transcript(provider, auth_home, conversation_id)
        if path:
            page["resolution_method"] = "conversation_id"
        elif fallback_to_recency:
            page["resolution_scope"] = scope
            path, page["resolution_method"] = resolve_transcript(provider, auth_home, started_at, cwd=scope["cwd"])
    else:
        page["resolution_scope"] = scope
        path, page["resolution_method"] = resolve_transcript(provider, auth_home, started_at, terminal_transcript=terminal_transcript, cwd=scope["cwd"])
    if not path:
        reason = "no_conversation_yet" if page["resolution_scope"] is not None else "transcript_not_found"
        return {**page, "status": "unavailable", "reason": reason}
    try:
        with open(path, "rb") as handle:
            stat = os.fstat(handle.fileno())
            if _file_identity is not None and (stat.st_dev, stat.st_ino) != _file_identity:
                return {**page, "status": "unavailable", "reason": "evidence_changed"}
            identity = hashlib.sha256(f"{provider}:{os.path.realpath(path)}:{stat.st_dev}:{stat.st_ino}".encode()).hexdigest()
            if tail is not None or before is not None:
                return _read_tail(handle, stat, identity, provider, page, tail if tail is not None else limit, before)
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
                    entries = [entry] if entry is not None else []
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
            page["next_cursor"] = _encode_cursor(handle, identity, offset, index, names)
            return page
    except OSError:
        return {**page, "status": "unavailable", "reason": "transcript_unreadable", "entries": []}
