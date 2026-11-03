"""Conversation CLI parsing and JSON envelope contracts."""

import io
import json
import os
from pathlib import Path

import pytest

from src.cli import main
from src.commands.conversation import handle_conversation
from src.errors import CdxError


def test_cli_page_and_resume(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / "example.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes((Path(__file__).parent / "fixtures" / "conversation" / "claude.jsonl").read_bytes())
    session = {"name": "work", "provider": "claude", "authHome": str(tmp_path), "conversation": {"id": "example"}}
    service = {"get_session": lambda name: session if name == "work" else None}
    stdout = io.StringIO()
    options = {"stdout": stdout, "stderr": io.StringIO(), "service": service}
    assert main(["conversation", "work", "--limit=2", "--json"], options) == 0
    first = json.loads(stdout.getvalue())
    assert first["resolution_method"] == "conversation_id"
    assert first["ok"] and first["action"] == "conversation"
    assert first["session"] == "work" and len(first["entries"]) == 2
    stdout.seek(0)
    stdout.truncate()
    assert main(["conversation", "work", "--cursor", first["next_cursor"], "--json"], options) == 0
    second = json.loads(stdout.getvalue())
    assert len(second["entries"]) == 3
    assert second["entries"][0]["tool_name"] == "Bash"


@pytest.mark.parametrize("args", [[], ["work"], ["work", "--json", "--limit", "bad"], ["work", "--json", "--limit", "0"], ["work", "--json", "--unknown"], ["missing", "--json"]])
def test_invalid_arguments(args):
    ctx = {"service": {"get_session": lambda name: None if name == "missing" else {"name": name, "provider": "codex"}}, "stdout": io.StringIO()}
    with pytest.raises(CdxError):
        handle_conversation(args, ctx)


def test_unsupported_provider_json():
    stdout = io.StringIO()
    ctx = {"service": {"get_session": lambda name: {"name": name, "provider": "ollama"}}, "out": stdout.write}
    assert handle_conversation(["local", "--json"], ctx) == 0
    assert json.loads(stdout.getvalue())["status"] == "unsupported"


@pytest.mark.parametrize("recorded_id", [None, "remote-only"])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("provider", ["codex", "claude", "antigravity"])
def test_local_recency_only_for_implicit_conversations(tmp_path, recorded_id, explicit, provider):
    local_id = "11111111-1111-4111-8111-111111111111"
    if provider == "codex":
        path = tmp_path / "sessions" / f"rollout-{local_id}.jsonl"
    else:
        path = tmp_path / ".claude" / "projects" / "repo" / f"{local_id}.jsonl"
    path.parent.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "conversation" / f"{provider}.jsonl"
    path.write_bytes(fixture.read_bytes())
    older = path.with_name(path.name.replace(local_id, "22222222-2222-4222-8222-222222222222"))
    older.write_text('{}\n')
    os.utime(older, (1, 1))
    session = {"name": "work", "provider": provider, "authHome": str(tmp_path)}
    if recorded_id:
        session["conversation"] = {"id": recorded_id, "provenance": "imposed"}
    before = json.dumps(session)
    output = io.StringIO()
    ctx = {"service": {"get_session": lambda name: session}, "out": output.write}
    args = ["work", "--json", *(["--conversation", "missing-explicit"] if explicit else [])]
    assert handle_conversation(args, ctx) == 0
    page = json.loads(output.getvalue())
    assert page["status"] == ("unavailable" if explicit else "ok")
    assert page["resolution_method"] == (None if explicit else "recency")
    if explicit:
        assert page["reason"] == "transcript_not_found" and page["entries"] == []
    else:
        assert page["entries"][0]["text"] == "Hello café"
    assert json.dumps(session) == before
