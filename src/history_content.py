"""Bounded provider evidence for resumable interactive history rows."""

import json
import os
import re
import shlex
import time

from .conversation import MAX_LINE_BYTES, MAX_PAGE_BYTES, _entries, _redact
from .interactive_usage import (
    MAX_TRANSCRIPT_CANDIDATES,
    MAX_TRANSCRIPT_SCAN_SECONDS,
    _timestamp,
    conversation_transcript,
    resolve_transcript,
)

_WRAPPERS = re.compile(
    r"<(?P<tag>local-command-caveat|command-name|command-message|command-args|local-command-stdout|"
    r"local-command-stderr|system-reminder|environment_context|instructions)>.*?</(?P=tag)>", re.S,
)


def _identity_arg(args):
    args = list(args or [])
    if "-c" in args:
        index = args.index("-c") + 1
        try:
            args = shlex.split(args[index])
        except (IndexError, ValueError, TypeError):
            return None
    for index, arg in enumerate(args):
        if arg == "--":
            break
        if arg in ("--session-id", "--resume", "resume") and index + 1 < len(args):
            identifier = args[index + 1]
            if isinstance(identifier, str) and re.fullmatch(r"[0-9a-fA-F-]{36}", identifier):
                return identifier
    return None


def clean_prompt(text):
    text = _WRAPPERS.sub("", text).strip()
    lines = [line for line in text.splitlines() if not re.fullmatch(
        r"\s*(?:(?:/|~/|[A-Za-z]:[\\/]|\.\.?[/\\])\S+|[\w./\\-]+\.[A-Za-z0-9]{1,10})\s*", line)]
    return _redact("\n".join(lines).strip())


def first_user_prompt(provider, path):
    if not path:
        return None
    try:
        with open(path, "rb") as handle:
            scanned = 0
            names = {}
            while scanned < MAX_PAGE_BYTES:
                line = handle.readline(MAX_LINE_BYTES + 1)
                if not line:
                    break
                scanned += len(line)
                if len(line) > MAX_LINE_BYTES:
                    return None
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeError, RecursionError):
                    continue
                texts = [clean_prompt(entry["text"]) for entry in _entries(provider, record, names)
                         if entry["role"] == "user"]
                text = "\n".join(text for text in texts if text)
                if text:
                    return text[:2000]
    except OSError:
        pass
    return None


def _new_codex_id(auth_home, entry):
    """Only a unique rollout created in this launch's project/time can identify it."""
    start = _timestamp(entry.get("started_at"))
    end = _timestamp(entry.get("ended_at"))
    cwd = entry.get("cwd")
    if start is None or not cwd:
        return None
    deadline = time.monotonic() + MAX_TRANSCRIPT_SCAN_SECONDS
    found = set()
    count = 0
    for directory, _, names in os.walk(os.path.join(auth_home, "sessions")):
        if time.monotonic() >= deadline:
            return None
        for name in names:
            if time.monotonic() >= deadline:
                return None
            if not name.endswith(".jsonl"):
                continue
            count += 1
            if count > MAX_TRANSCRIPT_CANDIDATES:
                return None
            try:
                with open(os.path.join(directory, name), encoding="utf-8") as handle:
                    record = json.loads(handle.readline(64 * 1024))
                payload = record.get("payload") or {}
                stamp = _timestamp(record.get("timestamp") or payload.get("timestamp"))
                identifier = payload.get("id") or payload.get("session_id")
                if (record.get("type") == "session_meta" and stamp is not None and stamp >= start
                        and (end is None or stamp <= end) and isinstance(payload.get("cwd"), str)
                        and os.path.realpath(payload["cwd"]) == os.path.realpath(cwd)
                        and isinstance(identifier, str) and conversation_transcript("codex", auth_home, identifier)):
                    found.add(identifier)
            except (OSError, ValueError, TypeError, AttributeError, RecursionError):
                continue
    return next(iter(found)) if len(found) == 1 else None


def enrich_history(entry, session):
    entry = dict(entry)
    provider = entry.get("provider") or session.get("provider")
    home = session.get("authHome")
    if provider not in ("claude", "codex") or not home:
        return entry
    identifier = entry.get("conversation_id")
    if not identifier:
        identifier = _identity_arg(entry.get("args")) if entry.get("action") != "run" else None
    if not identifier and provider == "codex" and entry.get("action") != "run":
        identifier = _new_codex_id(home, entry)
    path = conversation_transcript(provider, home, identifier) if identifier else None
    if path:
        entry.update(conversation_id=identifier, provider_transcript_path=path,
                     provider_transcript_match="conversation_id")
    elif identifier:
        # A known identity whose transcript is absent must never target another session.
        entry["conversation_id"] = identifier
        path = None
    else:
        path = entry.get("provider_transcript_path")
        if not path and entry.get("action") != "run":
            path, _ = resolve_transcript(provider, home, entry.get("started_at"), cwd=entry.get("cwd"))
        if path and entry.get("action") != "run":
            entry.update(provider_transcript_path=path, provider_transcript_match="recency")
    prompt = first_user_prompt(provider, path)
    if prompt:
        entry["first_user_prompt"] = prompt
    elif entry.get("first_user_prompt"):
        entry["first_user_prompt"] = clean_prompt(entry["first_user_prompt"]) or None
    return entry
