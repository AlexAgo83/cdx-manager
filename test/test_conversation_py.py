"""Provider fixtures and incremental conversation reader contracts."""

import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.conversation import MAX_LINE_BYTES, read_conversation
from src.errors import CdxError

FIXTURES = Path(__file__).parent / "fixtures" / "conversation"
CONVERSATION = "11111111-1111-4111-8111-111111111111"


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
    assert read_conversation(provider, str(home))["entries"]


@pytest.mark.parametrize("limit", [0, -1, 1001, "2", True])
def test_invalid_limit(limit):
    with pytest.raises(CdxError):
        read_conversation("codex", limit=limit)


def test_redaction_and_oversized_record(transcript):
    provider, _, path = transcript
    text = 'api_key="fake-value-for-testing" Bearer fake-bearer-value'
    message = {"role": "user", "content": text}
    record = {"type": "response_item", "payload": {"type": "message", **message}} if provider == "codex" else {"type": "user", "message": message}
    path.write_text(json.dumps(record) + "\n")
    page = read(transcript)
    assert "fake-value" not in json.dumps(page)
    assert "fake-bearer" not in json.dumps(page)
    assert "[REDACTED]" in page["entries"][0]["text"]
    path.write_bytes(b"x" * (MAX_LINE_BYTES + 1))
    assert read(transcript)["reason"] == "record_too_large"


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
