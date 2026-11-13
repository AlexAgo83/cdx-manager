"""Provider fixtures and incremental conversation reader contracts."""

import base64
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.conversation import MAX_CURSOR_NAMES_BYTES, MAX_LINE_BYTES, read_conversation
from src.errors import CdxError

FIXTURES = Path(__file__).parent / "fixtures" / "conversation"
CONVERSATION = "11111111-1111-4111-8111-111111111111"


HARNESS_EXPECTED = [
    [], [], [], [], [], [], [], [], [],
    ["Please check the parser."], ["Please inspect this image."], [""], [""],
    ["Please explain '<task-notification>' in this normal sentence."],
    ["The user sent a new message while you were working:\nThis is my example without a closing wrapper."],
    ["Please quote this line:\nThe user sent a new message while you were working:\n\nExample\n\n"
     "This is how Claude Code surfaces messages the user sends mid-turn so you can respond without losing your place. "
     "Address the message above as you continue this turn."],
    ["<task-notification>Example</task-notification> is markup I want explained."],
    ["Keep my actual message."], ["First paragraph.", "Second paragraph."],
    ["<task-notification>First</task-notification> is followed by <task-notification>Second</task-notification>"],
    [], [""], [""],
]


@pytest.mark.parametrize("index, expected", list(enumerate(HARNESS_EXPECTED)), ids=[
    "background-task", "monitor", "stdout", "stderr", "command-blocks", "command-message", "command-args",
    "reminder", "multiple-blocks", "mid-turn-text", "mid-turn-text-image", "mid-turn-image", "normal-image",
    "quoted-tag", "incomplete-wrapper", "quoted-wrapper", "markup-with-prose", "reminder-with-user-text",
    "mid-turn-split-text", "prose-between-tags",
    "mid-turn-empty", "mid-turn-image-single-text", "reminder-with-image",
])
def test_claude_harness_records(tmp_path, index, expected):
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text((FIXTURES / "claude-harness.jsonl").read_text().splitlines()[index] + "\n")
    page = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION)
    assert [e["text"] for e in page["entries"]] == expected
    assert all(e["role"] == "user" and e["at"] == "2026-11-04T10:00:00Z" for e in page["entries"])
    assert "ZmFrZS1pbWFnZQ==" not in json.dumps(page)


def test_claude_harness_paging(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes((FIXTURES / "claude-harness.jsonl").read_bytes())
    transcript = ("claude", tmp_path, path)
    whole = read(transcript)["entries"]
    assert [e["text"] for e in whole] == [text for texts in HARNESS_EXPECTED for text in texts]
    cursor, forward = None, []
    while True:
        page = read(transcript, cursor=cursor, limit=1)
        forward.extend(page["entries"])
        cursor = page["next_cursor"]
        if not page["has_more"]:
            break
    assert forward == whole
    assert read(transcript, cursor=cursor)["entries"] == []
    page = read(transcript, tail=1)
    backward = page["entries"]
    while page["before_cursor"]:
        page = read(transcript, before=page["before_cursor"], limit=1)
        backward = page["entries"] + backward
    assert backward == whole


@pytest.fixture(params=["codex", "claude", "antigravity"])
def transcript(request, tmp_path):
    provider = request.param
    if provider == "codex":
        path = tmp_path / "sessions" / "2026" / f"rollout-2026-11-03-{CONVERSATION}.jsonl"
    else:
        path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes((FIXTURES / f"{provider}.jsonl").read_bytes())
    return provider, tmp_path, path


def read(transcript, **kwargs):
    provider, home, _ = transcript
    return read_conversation(provider, str(home), conversation_id=CONVERSATION, **kwargs)


def test_fixture_and_cursor_resume(transcript):
    whole = read(transcript)
    assert whole["status"] == "ok"
    assert [e["role"] for e in whole["entries"]] == ["user", "tool", "tool", "assistant", "assistant"]
    assert whole["entries"][0]["text"] == "Hello café"
    assert whole["entries"][0]["at"] == "2026-11-03T10:00:00Z"
    assert whole["entries"][1]["tool_name"] == whole["entries"][2]["tool_name"]
    assert "private" not in json.dumps(whole)
    entries, cursor = [], None
    for _ in range(5):
        page = read(transcript, cursor=cursor, limit=1)
        entries.extend(page["entries"])
        cursor = page["next_cursor"]
    assert entries == whole["entries"]
    assert read(transcript, cursor=cursor)["entries"] == []
    assert set(entries[0]) == {"role", "text", "tool_name", "tool_summary", "at", "id"}


def test_append_partial_line_and_skip_malformed_records(transcript):
    cursor = read(transcript)["next_cursor"]
    provider, _, path = transcript
    message = {"role": "assistant", "content": "Live response"}
    record = {"type": "response_item", "payload": {"type": "message", **message}} if provider == "codex" else {"type": "assistant", "message": message}
    with path.open("ab") as handle:
        handle.write(b'not json\n[]\n' + json.dumps(record).encode())
    partial = read(transcript, cursor=cursor)
    assert partial["entries"] == []
    assert partial["has_more"]
    with path.open("ab") as handle:
        handle.write(b'\n')
    page = read(transcript, cursor=partial["next_cursor"])
    assert [e["text"] for e in page["entries"]] == ["Live response"]
    assert not page["has_more"]


def test_cursor_rejects_truncation_replacement_and_invalid_input(transcript):
    cursor = read(transcript)["next_cursor"]
    for invalid in ("bad", "W10=", base64.urlsafe_b64encode(b'null').decode()):
        assert read(transcript, cursor=invalid)["status"] == "reset_required"
    _, _, path = transcript
    original = path.read_bytes()
    path.write_bytes(b"")
    assert read(transcript, cursor=cursor)["status"] == "reset_required"
    path.unlink()
    path.write_bytes(original)
    # File replacement is detected even when its contents have the same size.
    # Some filesystems reuse an inode immediately, so replace a still-live file.
    cursor = read(transcript)["next_cursor"]
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(original)
    replacement.replace(path)
    assert read(transcript, cursor=cursor)["status"] == "reset_required"


def test_reader_seeks_instead_of_replaying_history(transcript):
    cursor = read(transcript)["next_cursor"]
    _, _, path = transcript
    opened = []

    real_open = open

    class Wrapper:
        def __enter__(self):
            self.handle = real_open(path, "rb")
            return self

        def __exit__(self, *args):
            self.handle.close()

        def __getattr__(self, key):
            return getattr(self.handle, key)

        def readline(self, size):
            opened.append(self.handle.tell())
            return self.handle.readline(size)

    with patch("src.conversation.open", return_value=Wrapper()):
        assert read(transcript, cursor=cursor)["entries"] == []
    assert opened == [path.stat().st_size]


def test_unavailable_and_ollama_fixture(tmp_path):
    for provider in ("codex", "claude", "antigravity"):
        assert read_conversation(provider, str(tmp_path))["status"] == "unavailable"
    for cursor in (None, "unused"):
        page = read_conversation("ollama", str(tmp_path), terminal_transcript=str(FIXTURES / "ollama.log"), cursor=cursor)
        assert page["status"] == "unsupported"
        assert page["entries"] == []
    assert read_conversation("ollama")["status"] == "unsupported"
    assert read_conversation("unknown")["status"] == "unsupported"


def test_exact_conversation_does_not_read_another_file(transcript):
    provider, home, _ = transcript
    assert read_conversation(provider, str(home), conversation_id="missing")["status"] == "unavailable"
    assert read_conversation(provider, str(home))["reason"] == "no_conversation_yet"


@pytest.mark.parametrize("limit", [0, -1, 1001, "2", True])
def test_invalid_limit(limit):
    with pytest.raises(CdxError):
        read_conversation("codex", limit=limit)


def test_redaction(transcript):
    provider, _, path = transcript
    text = 'api_key="fake-value-for-testing" Bearer fake-bearer-value'
    message = {"role": "user", "content": text}
    record = {"type": "response_item", "payload": {"type": "message", **message}} if provider == "codex" else {"type": "user", "message": message}
    path.write_text(json.dumps(record) + "\n")
    page = read(transcript)
    assert "fake-value" not in json.dumps(page)
    assert "fake-bearer" not in json.dumps(page)
    assert "[REDACTED]" in page["entries"][0]["text"]


def _message_record(provider, role, text):
    message = {"role": role, "content": text}
    return {"type": "response_item", "payload": message} if provider == "codex" else {"type": role, "message": message}


def _append_oversized_record(path, provider, complete=True):
    field = "payload" if provider == "codex" else "message"
    with path.open("ab") as handle:
        kind = 'response_item' if provider == 'codex' else 'user'
        handle.write((' {"type": "' + kind + '", "' + field + '": {"role": "user", "content": [{"type": "image", "source": "').encode())
        for _ in range(20):
            handle.write(b"x" * (1024 * 1024))
        if complete:
            handle.write(b'"}]}}\n')


def test_oversized_middle_record_and_cursor_before_it(transcript):
    provider, _, path = transcript
    path.write_text(json.dumps(_message_record(provider, "assistant", "Before")) + "\n")
    before = read(transcript, limit=1)
    _append_oversized_record(path, provider)
    with path.open("ab") as handle:
        handle.write((json.dumps(_message_record(provider, "assistant", "After")) + "\n").encode())

    real_open = open
    sizes = []

    class BoundedReader:
        def __enter__(self):
            self.handle = real_open(path, "rb")
            return self

        def __exit__(self, *args):
            self.handle.close()

        def __getattr__(self, key):
            return getattr(self.handle, key)

        def readline(self, size=-1):
            assert 0 < size <= MAX_LINE_BYTES + 1
            sizes.append(size)
            return self.handle.readline(size)

        def read(self, size=-1):
            assert 0 < size <= MAX_LINE_BYTES + 1
            return self.handle.read(size)

    with patch("src.conversation.open", return_value=BoundedReader()):
        middle = read(transcript, cursor=before["next_cursor"])
    assert len(sizes) > 20
    assert middle["status"] == "ok"
    assert middle["has_more"]
    skipped = middle["entries"][0]
    assert skipped["role"] == "user"
    assert skipped["text"] == "[élément trop volumineux ignoré]"
    assert len(json.dumps(middle)) < 4096
    assert json.loads(base64.urlsafe_b64decode(middle["next_cursor"]))["offset"] > 20 * 1024 * 1024
    assert read(transcript)["entries"] == before["entries"] + [skipped]
    after = read(transcript, cursor=middle["next_cursor"])
    assert [e["text"] for e in after["entries"]] == ["After"]
    assert not after["has_more"]


def test_oversized_incomplete_final_record_is_retried(transcript):
    provider, _, path = transcript
    cursor = read(transcript)["next_cursor"]
    _append_oversized_record(path, provider, complete=False)
    for _ in range(2):
        page = read(transcript, cursor=cursor)
        assert page["status"] == "ok"
        assert page["entries"] == []
        assert page["has_more"]
        assert page["next_cursor"] == cursor
    with path.open("ab") as handle:
        handle.write(b'"}]}}\n')
    page = read(transcript, cursor=page["next_cursor"])
    assert [e["text"] for e in page["entries"]] == ["[élément trop volumineux ignoré]"]
    assert not page["has_more"]
    assert read(transcript, cursor=page["next_cursor"])["entries"] == []


@pytest.mark.parametrize("prefix,role", [
    (b'{"type":"assistant","message":{"role":"assistant","content":"', "assistant"),
    (b'{"type":"user","message":{"content":"', "user"),
    (b'{"type":"assistant","message":{"content":"role: user ', "assistant"),
    (b'{"type":"assistant","metadata":{"role":"user"},"message":{"content":"', "assistant"),
    (b'{"type":"unknown","message":{"content":"', None),
    (b'{"type":"user","message":{"role":"system","content":"', "tool"),
    (b'{"message":{"role":"user","content":"', None),
    (b'{"type":"api-request-blob","message":{"role":"user","content":"', None),
    (b'{"type":"user","message":"', None),
    (b'{"type":"user","content":"', None),
])
def test_oversized_role_uses_only_structural_metadata(tmp_path, prefix, role):
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(prefix + b"x" * MAX_LINE_BYTES + b'"}}\n')
    page = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION)
    if role is None:
        assert page["entries"] == []
    else:
        assert page["entries"][0]["role"] == role


def test_legacy_cursor_names_are_accepted_and_bounded(transcript):
    state = json.loads(base64.urlsafe_b64decode(read(transcript)["next_cursor"]))
    state["names"] = {hashlib.sha256(str(i).encode()).hexdigest(): "tool_" + "x" * 95 for i in range(100)}
    cursor = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    page = read(transcript, cursor=cursor)
    assert page["status"] == "ok"
    assert len(page["next_cursor"]) < 4096
    compacted = json.loads(base64.urlsafe_b64decode(page["next_cursor"]))
    assert compacted["v"] == 1
    assert len(json.dumps(compacted["names"], separators=(",", ":")).encode()) <= MAX_CURSOR_NAMES_BYTES
    assert list(compacted["names"].items()) == list(state["names"].items())[-len(compacted["names"]):]
    assert read(transcript, cursor=page["next_cursor"])["status"] == "ok"


def test_cursor_cannot_echo_arbitrary_metadata(transcript):
    state = json.loads(base64.urlsafe_b64decode(read(transcript)["next_cursor"]))
    state["names"] = {"bad": "fake-sensitive-content"}
    cursor = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    page = read(transcript, cursor=cursor)
    assert page["status"] == "reset_required"
    assert page["next_cursor"] is None


def test_unreadable_file(transcript):
    with patch("src.conversation.open", side_effect=PermissionError):
        assert read(transcript)["reason"] == "transcript_unreadable"


def test_codex_builtin_tools_and_event_duplicates(tmp_path):
    path = tmp_path / "sessions" / f"rollout-test-{CONVERSATION}.jsonl"
    path.parent.mkdir()
    records = [
        {"type": "response_item", "payload": {"type": "web_search_call", "action": {"query": "private query"}}},
        {"type": "event_msg", "payload": {"type": "agent_message", "message": "duplicate"}},
        {"type": "response_item", "payload": {"type": "reasoning", "summary": "private reasoning"}},
    ]
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    page = read_conversation("codex", str(tmp_path), conversation_id=CONVERSATION)
    assert len(page["entries"]) == 1
    assert page["entries"][0]["tool_name"] == "web_search"
    assert "private" not in json.dumps(page)


def test_tail_matches_forward_normalization_and_before_blocks(transcript):
    expected = read(transcript)["entries"]
    page = read(transcript, tail=1)
    collected = page["entries"]
    assert collected == expected[-1:]
    while page["before_cursor"]:
        page = read(transcript, before=page["before_cursor"], limit=1)
        assert page["status"] == "ok"
        collected = page["entries"] + collected
    assert collected == expected
    assert read(transcript, tail=1000)["entries"] == expected
    assert read(transcript, tail=1000)["before_cursor"] is None


def test_tail_large_transcript_measures_bounded_reads(transcript, record_property):
    provider, _, path = transcript
    path.write_text("".join(json.dumps(_message_record(provider, "assistant", f"Message {i} café")) + "\n"
                            for i in range(6000)))
    real_open = open
    measured = {"bytes": 0, "max_read": 0}

    class MeasuredReader:
        def __enter__(self):
            self.handle = real_open(path, "rb")
            return self

        def __exit__(self, *args):
            self.handle.close()

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def read(self, size=-1):
            assert 0 <= size <= MAX_LINE_BYTES + 1
            data = self.handle.read(size)
            measured["bytes"] += len(data)
            measured["max_read"] = max(measured["max_read"], size)
            return data

        def readline(self, size=-1):
            raise AssertionError("Initial tail must use reverse block reads")

    with patch("src.conversation.open", return_value=MeasuredReader()):
        page = read(transcript, tail=25)
    record_property("tail_bytes_read", measured["bytes"])
    record_property("transcript_bytes", path.stat().st_size)
    assert measured["bytes"] < path.stat().st_size // 4
    assert measured["max_read"] <= 64 * 1024
    assert [e["text"] for e in page["entries"]] == [f"Message {i} café" for i in range(5975, 6000)]
    entries = page["entries"]
    for _ in range(61):
        if page["before_cursor"] is None:
            break
        page = read(transcript, before=page["before_cursor"])
        entries = page["entries"] + entries
    assert page["before_cursor"] is None
    assert len(entries) == 6000
    assert len({e["id"] for e in entries}) == 6000
    assert [e["text"] for e in entries] == [f"Message {i} café" for i in range(6000)]


def test_tail_next_cursor_and_partial_append(transcript):
    provider, _, path = transcript
    page = read(transcript, tail=2)
    with path.open("ab") as handle:
        handle.write(json.dumps(_message_record(provider, "assistant", "New café")).encode())
    partial = read(transcript, tail=2)
    assert partial["entries"] == page["entries"]
    with path.open("ab") as handle:
        handle.write(b"\n")
    assert [e["text"] for e in read(transcript, cursor=page["next_cursor"])["entries"]] == ["New café"]
    assert [e["text"] for e in read(transcript, cursor=partial["next_cursor"])["entries"]] == ["New café"]
    assert read(transcript, before=page["before_cursor"])["status"] == "ok"


def test_tail_oversized_record_and_incomplete_tail(transcript):
    provider, _, path = transcript
    expected = read(transcript)["entries"]
    _append_oversized_record(path, provider)
    with path.open("ab") as handle:
        handle.write((json.dumps(_message_record(provider, "assistant", "After")) + "\n").encode())
    page = read(transcript, tail=3)
    assert page["entries"][0] == expected[-1]
    assert [e["text"] for e in page["entries"]][1:] == ["[élément trop volumineux ignoré]", "After"]
    previous = read(transcript, before=page["before_cursor"], limit=100)
    assert previous["entries"] == expected[:-1]
    _append_oversized_record(path, provider, complete=False)
    assert read(transcript, tail=3)["entries"] == page["entries"]
    with path.open("ab") as handle:
        handle.write(b'"}]}}\n')
    assert len(read(transcript, cursor=page["next_cursor"])["entries"]) == 1


def test_before_rejects_rewrite_and_wrong_cursor(transcript):
    page = read(transcript, tail=1)
    assert read(transcript, before=page["next_cursor"])["status"] == "reset_required"
    assert read(transcript, before="invalid")["status"] == "reset_required"
    _, _, path = transcript
    original = path.read_bytes()
    path.write_bytes(original.replace(b"Hello", b"Hallo"))
    assert read(transcript, before=page["before_cursor"])["status"] == "reset_required"
    path.write_bytes(b"")
    assert read(transcript, before=page["before_cursor"])["status"] == "reset_required"


@pytest.mark.parametrize("tail", [0, -1, 1001, True, "2"])
def test_invalid_tail(tail):
    with pytest.raises(CdxError):
        read_conversation("codex", tail=tail)


@pytest.mark.parametrize("kwargs", [{"tail": 2}, {"before": "invalid"}])
def test_tail_rejects_forward_cursor_combination(kwargs):
    with pytest.raises(CdxError):
        read_conversation("codex", cursor="invalid", **kwargs)


def test_tail_next_cursor_retains_preceding_tool_names(transcript):
    provider, _, path = transcript
    whole = read(transcript)
    page = read(transcript, tail=1)
    if provider == "codex":
        record = {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call-1"}}
    else:
        record = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call-1"}]}}
    # Match the fixture's real call identifier without exposing tool bodies.
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for original in records:
        message = original.get("payload", {}) if provider == "codex" else original.get("message", {})
        if provider == "codex" and message.get("type") == "function_call":
            record["payload"]["call_id"] = message["call_id"]
        for block in message.get("content", []) if isinstance(message.get("content"), list) else []:
            if block.get("type") == "tool_use":
                record["message"]["content"][0]["tool_use_id"] = block["id"]
    with path.open("ab") as handle:
        handle.write((json.dumps(record) + "\n").encode())
    followed = read(transcript, cursor=page["next_cursor"])
    assert followed["entries"][0]["tool_name"] == whole["entries"][1]["tool_name"]


def test_before_rejects_invalid_block_index_and_replacement(transcript):
    page = read(transcript, tail=1)
    state = json.loads(base64.urlsafe_b64decode(page["before_cursor"]))
    state["index"] = MAX_LINE_BYTES
    invalid = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    assert read(transcript, before=invalid)["status"] == "reset_required"
    _, _, path = transcript
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(path.read_bytes())
    replacement.replace(path)
    assert read(transcript, before=page["before_cursor"])["status"] == "reset_required"


def test_tail_empty_and_non_message_records(transcript):
    _, _, path = transcript
    for body in (b"", b"{}\nnot json\n[]\n", b'{"unfinished":'):
        path.write_bytes(body)
        page = read(transcript, tail=10)
        assert page["entries"] == []
        assert page["before_cursor"] is None
        assert read(transcript, cursor=page["next_cursor"])["entries"] == []


def test_claude_request_blob_incident(transcript):
    provider, _, path = transcript
    if provider == "codex":
        pytest.skip("Claude-compatible transcript format")
    path.write_bytes((FIXTURES / "claude-request-blob.jsonl").read_bytes())
    page = read(transcript)
    assert [(e["role"], e["text"], e["tool_name"]) for e in page["entries"]] == [
        ("user", "Check the conversation reader", None),
        ("tool", "", "Read"),
        ("tool", "", "Read"),
        ("assistant", "The reader is fixed", None),
    ]
    assert all(e["at"] is not None for e in page["entries"])
    cursor, entries = None, []
    while True:
        part = read(transcript, cursor=cursor, limit=1)
        entries.extend(part["entries"])
        cursor = part["next_cursor"]
        if not part["has_more"]:
            break
    assert entries == page["entries"]
    assert read(transcript, cursor=cursor)["entries"] == []


@pytest.mark.parametrize("kind", [
    "api-request-blob", "summary", "queue-operation", "file-history-snapshot",
    "last-prompt", "attachments", "system", "event_msg", "session_meta", "unknown", None,
])
@pytest.mark.parametrize("oversized", [False, True])
@pytest.mark.parametrize("mode", ["forward", "tail", "before"])
def test_only_conversation_record_types_are_read(transcript, kind, oversized, mode):
    provider, _, path = transcript
    message = {"role": "user", "content": "x" * MAX_LINE_BYTES if oversized else "Duplicate"}
    record = {"type": kind, "message": message, "payload": message}
    after = _message_record(provider, "assistant", "After")
    after["timestamp"] = "2026-11-04T10:00:00Z"
    path.write_text(json.dumps(record) + "\n" + json.dumps(after) + "\n")
    if mode == "before":
        with path.open("a") as handle:
            handle.write(json.dumps(_message_record(provider, "assistant", "Latest")) + "\n")
        latest = read(transcript, tail=1)
        page = read(transcript, before=latest["before_cursor"], limit=1000)
        assert page["before_cursor"] is None
        assert read(transcript, cursor=page["next_cursor"])["entries"] == latest["entries"]
    else:
        page = read(transcript, **({"tail": 1000} if mode == "tail" else {"limit": 1}))
        assert read(transcript, cursor=page["next_cursor"])["entries"] == []
    assert [(e["text"], e["at"]) for e in page["entries"]] == [("After", after["timestamp"])]
    assert page["has_more"] == (mode == "before")


def test_claude_queued_messages_typed_mid_turn_are_user_entries(tmp_path):
    # Claude Code stores messages typed while the agent works only as queued_command attachments.
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    at = "2026-11-05T19:55:18Z"
    def queued(prompt, kind="human"):
        return json.dumps({"type": "attachment", "timestamp": at, "attachment": {
            "type": "queued_command", "prompt": prompt, "origin": {"kind": kind}, "humanTurn": True}})
    image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "ZmFrZS1pbWFnZQ=="}}
    big = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A" * (MAX_LINE_BYTES + 10)}}
    path.write_text("\n".join([
        queued("ah mais je ne vois plus aucun de mes messages"),
        queued("<task-notification>done</task-notification>", kind="task"),
        queued([{"type": "text", "text": "[Image #5] bloqué sur signaler"}, image]),
        queued([{"type": "text", "text": "[Image #6] capture lourde"}, big]),
        json.dumps({"type": "attachment", "timestamp": at, "attachment": {"type": "hook_success"}}),
        # Print mode (cdx remote control) leaves the origin out of an operator prompt.
        json.dumps({"type": "attachment", "timestamp": at, "attachment": {
            "type": "queued_command", "prompt": "je test le msg queue", "commandMode": "prompt", "hostsOwnTurn": True}}),
        json.dumps({"type": "attachment", "timestamp": at, "attachment": {
            "type": "queued_command", "prompt": "<task-notification>x</task-notification>", "commandMode": "task-notification"}}),
    ]) + "\n")
    page = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION)
    assert [(e["role"], e["text"]) for e in page["entries"]] == [
        ("user", "ah mais je ne vois plus aucun de mes messages"),
        ("user", "[Image #5] bloqué sur signaler"),
        ("user", "[Image #6] capture lourde"),
        ("user", "je test le msg queue"),
    ]
    assert "ZmFrZS1pbWFnZQ==" not in json.dumps(page)
    tail = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION, tail=10)
    assert [e["text"] for e in tail["entries"]] == [e["text"] for e in page["entries"]]


def test_claude_meta_user_records_are_not_operator_messages(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    at = "2026-11-06T08:58:56Z"
    path.write_text("\n".join([
        json.dumps({"type": "user", "isMeta": True, "timestamp": at, "message": {"role": "user",
            "content": "[Image: original 1366x3002, displayed at 1172x2576. Multiply coordinates by 1.17 to map to original image.]"}}),
        json.dumps({"type": "user", "timestamp": at, "message": {"role": "user", "content": "oula"}}),
    ]) + "\n")
    page = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION)
    assert [(e["role"], e["text"]) for e in page["entries"]] == [("user", "oula")]


def test_claude_oversized_tool_result_is_a_tool_entry(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    prefix = b'{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_1","type":"tool_result","content":[{"type":"image","source":{"data":"'
    path.write_bytes(prefix + b"x" * MAX_LINE_BYTES + b'"}}]}]}}\n')
    page = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION)
    assert [(e["role"], e["text"]) for e in page["entries"]] == [("tool", "")]


def test_claude_pasted_content_wrapper_is_removed(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / f"{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)
    text = '<pasted_content id="c1cc">\nOn est ok avec ces notifs ?\n/home/u/a.png\n</pasted_content id="c1cc">'
    quoted = 'a literal <pasted_content id="x1"> without its closing tag'
    path.write_text("\n".join(json.dumps({"type": "user", "timestamp": "2026-11-06T11:56:00Z",
        "message": {"role": "user", "content": value}}) for value in (text, quoted)) + "\n")
    page = read_conversation("claude", str(tmp_path), conversation_id=CONVERSATION)
    assert [e["text"] for e in page["entries"]] == ["On est ok avec ces notifs ?\n/home/u/a.png", quoted]


def test_codex_injected_context_is_not_a_user_turn(tmp_path):
    path = tmp_path / "sessions" / "2026" / f"rollout-2026-11-03-{CONVERSATION}.jsonl"
    path.parent.mkdir(parents=True)

    def message(role, *texts):
        kind = "output_text" if role == "assistant" else "input_text"
        return {"type": "response_item", "timestamp": "2026-11-03T10:00:00Z", "payload": {
            "type": "message", "role": role, "content": [{"type": kind, "text": text} for text in texts]}}

    records = [
        {"type": "session_meta", "payload": {"id": CONVERSATION, "source": "cli"}},
        message("developer", "You are Codex.", "<collaboration_mode>Default</collaboration_mode>"),
        message("user", "# AGENTS.md instructions for /repo\n\n<INSTRUCTIONS>\nrules\n</INSTRUCTIONS>",
                "<environment_context>\n  <cwd>/repo</cwd>\n</environment_context>"),
        message("user", "<user_instructions>\nolder layout\n</user_instructions>"),
        message("user", "Fix the build"),
        message("assistant", "Done."),
        message("user", "<turn_aborted>\ninterrupted\n</turn_aborted>"),
    ]
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    page = read_conversation("codex", str(tmp_path), conversation_id=CONVERSATION)
    assert [(e["role"], e["text"]) for e in page["entries"]] == [("user", "Fix the build"), ("assistant", "Done.")]
