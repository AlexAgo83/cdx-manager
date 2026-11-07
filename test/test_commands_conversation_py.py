"""Conversation CLI parsing and JSON envelope contracts."""

import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.cli import main
from src.commands.conversation import handle_conversation
from src.errors import CdxError
from src.shared_memory import claude_project_name


def test_cli_page_and_resume(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / "example.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes((Path(__file__).parent / "fixtures" / "conversation" / "claude.jsonl").read_bytes())
    session = {"name": "work", "provider": "claude", "authHome": str(tmp_path), "conversation": {"id": "example"}}
    service = {"get_session": lambda name: session if name == "work" else None}
    stdout = io.StringIO()
    options = {"stdout": stdout, "stderr": io.StringIO(), "service": service}
    assert main(["conversation", "work", "--limit=2", "--cwd", str(tmp_path / "another-project"),
                 "--since", "2099-01-01T00:00:00Z", "--json"], options) == 0
    first = json.loads(stdout.getvalue())
    assert first["resolution_method"] == "conversation_id"
    assert first["resolution_scope"] is None
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
def test_local_recency_only_for_implicit_conversations(tmp_path, recorded_id, explicit, provider, monkeypatch):
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.chdir(project)
    local_id = "11111111-1111-4111-8111-111111111111"
    if provider == "codex":
        path = tmp_path / "sessions" / f"rollout-{local_id}.jsonl"
    else:
        path = tmp_path / ".claude" / "projects" / claude_project_name(project) / f"{local_id}.jsonl"
    path.parent.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "conversation" / f"{provider}.jsonl"
    path.write_bytes(fixture.read_bytes())
    if provider == "codex":
        path.write_text(json.dumps({"type": "session_meta", "payload": {"cwd": str(project)}}) + "\n" + path.read_text())
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
    assert page["resolution_scope"] == (None if explicit else {"cwd": str(project), "since": None})
    if explicit:
        assert page["reason"] == "transcript_not_found" and page["entries"] == []
    else:
        assert page["entries"][0]["text"] == "Hello café"
    assert json.dumps(session) == before


def test_cli_tail_before_and_follow(tmp_path):
    path = tmp_path / ".claude" / "projects" / "example" / "example.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes((Path(__file__).parent / "fixtures" / "conversation" / "claude.jsonl").read_bytes())
    session = {"name": "work", "provider": "claude", "authHome": str(tmp_path), "conversation": {"id": "example"}}
    output = io.StringIO()
    ctx = {"service": {"get_session": lambda name: session}, "out": output.write}

    def invoke(*args):
        output.seek(0)
        output.truncate()
        assert handle_conversation(["work", "--json", *args], ctx) == 0
        return json.loads(output.getvalue())

    tail = invoke("--tail", "2")
    assert len(tail["entries"]) == 2
    previous = invoke("--before", tail["before_cursor"], "--limit", "3")
    assert len(previous["entries"]) == 3
    assert previous["before_cursor"] is None
    assert invoke("--cursor", tail["next_cursor"])["entries"] == []


@pytest.mark.parametrize("args", [
    ["--tail", "bad"], ["--tail", "0"], ["--tail", "1001"],
    ["--tail", "2", "--cursor", "invalid"], ["--before", "invalid", "--cursor", "invalid"],
])
def test_cli_invalid_tail_combinations(args):
    ctx = {"service": {"get_session": lambda name: {"name": name, "provider": "codex"}}}
    with pytest.raises(CdxError):
        handle_conversation(["work", "--json", *args], ctx)


@pytest.mark.parametrize("provider", ["claude", "codex", "antigravity"])
@pytest.mark.parametrize("recorded_id", [None, "missing-local"])
def test_recency_is_scoped_to_project_and_session_start(tmp_path, monkeypatch, provider, recorded_id):
    project = tmp_path / "cts"
    project.mkdir()
    monkeypatch.chdir(project)
    home = tmp_path / "profile"
    since = "2026-11-04T00:39:00Z"
    cutoff = datetime(2026, 11, 4, 0, 39, tzinfo=timezone.utc).timestamp()
    session = {"name": "grif", "provider": provider, "authHome": str(home)}
    if recorded_id:
        session["conversation"] = {"id": recorded_id}
    output = io.StringIO()
    ctx = {"service": {"get_session": lambda name: session}, "out": output.write}

    def write(directory, name, modified):
        if provider == "codex":
            path = home / "sessions" / "2026" / f"rollout-{name}.jsonl"
            metadata = {"type": "session_meta", "payload": {"cwd": str(directory)}}
            message = {"type": "response_item", "payload": {"role": "assistant", "content": name}}
            content = json.dumps(metadata) + "\n" + json.dumps(message) + "\n"
        else:
            path = home / ".claude" / "projects" / claude_project_name(directory) / f"{name}.jsonl"
            content = json.dumps({"type": "assistant", "message": {"content": name}}) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        os.utime(path, (modified, modified))
        return path

    def invoke(*args):
        output.seek(0)
        output.truncate()
        assert handle_conversation(["grif", "--json", *args], ctx) == 0
        return json.loads(output.getvalue())

    write(tmp_path / "remote-ops", "other-project", cutoff + 100)
    # A trust prompt has not produced a transcript in this project yet.
    page = invoke()
    assert page["status"] == "unavailable"
    assert page["reason"] == "no_conversation_yet"
    assert page["entries"] == [] and page["resolution_method"] is None
    assert page["resolution_scope"] == {"cwd": str(project), "since": None}

    write(project, "previous-session", cutoff - 1)
    page = invoke("--since", since)
    assert page["reason"] == "no_conversation_yet"
    assert page["resolution_scope"] == {"cwd": str(project), "since": since}

    write(project, "this-session", cutoff)
    page = invoke("--since", since)
    assert page["status"] == "ok" and page["resolution_method"] == "recency"
    assert [entry["text"] for entry in page["entries"]] == ["this-session"]
    # The explicit project wins over the process directory, including relative paths.
    page = invoke("--cwd", "../remote-ops", "--since", since)
    assert page["entries"][0]["text"] == "other-project"
    assert page["resolution_scope"] == {"cwd": str(tmp_path / "remote-ops"), "since": since}
    assert invoke("--since", since, "--conversation", "absent")["reason"] == "transcript_not_found"


@pytest.mark.parametrize("metadata", [None, {}, [], {"type": "session_meta", "payload": {}},
                                     {"type": "session_meta", "payload": {"cwd": "relative/project"}}])
def test_codex_recency_requires_session_cwd(tmp_path, metadata):
    path = tmp_path / "sessions" / "rollout-missing-cwd.jsonl"
    path.parent.mkdir()
    path.write_text(json.dumps(metadata) + "\n")
    session = {"name": "work", "provider": "codex", "authHome": str(tmp_path)}
    output = io.StringIO()
    ctx = {"service": {"get_session": lambda name: session}, "out": output.write}
    assert handle_conversation(["work", "--cwd", str(tmp_path), "--json"], ctx) == 0
    assert json.loads(output.getvalue())["reason"] == "no_conversation_yet"


def test_invalid_since_is_rejected():
    session = {"name": "work", "provider": "claude"}
    ctx = {"service": {"get_session": lambda name: session}}
    with pytest.raises(CdxError, match="ISO timestamp"):
        handle_conversation(["work", "--since", "yesterday", "--json"], ctx)


@pytest.mark.parametrize("selection", [["--pid", "123"], ["--process-identity", "opaque-identity"]])
def test_process_selection_ignores_saved_conversation(monkeypatch, selection):
    from src.commands import conversation

    session = {"name": "work2", "provider": "codex", "authHome": "/profile", "conversation": {"id": "old"}}
    calls = []

    def read(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "unavailable", "resolution_status": "unknown", "conversation_id": None,
                "resolution_method": None, "reason": "no_native_evidence", "entries": []}

    monkeypatch.setattr(conversation, "read_conversation", read)
    output = io.StringIO()
    ctx = {"service": {"get_session": lambda name: session}, "out": output.write}
    assert handle_conversation(["work2", *selection, "--json"], ctx) == 0
    assert calls[0]["conversation_id"] is None and calls[0]["fallback_to_recency"] is False
    assert calls[0]["pid"] == (123 if selection[0] == "--pid" else None)
    assert json.loads(output.getvalue())["resolution_status"] == "unknown"


@pytest.mark.parametrize("selection", [["--pid", "bad"], ["--pid", "123", "--process-identity", "opaque"],
                                      ["--pid", "123", "--conversation", "old"], ["--pid", "123", "--cwd", "/repo"]])
def test_process_selection_conflicts(selection):
    ctx = {"service": {"get_session": lambda name: {"name": name, "provider": "codex"}}}
    with pytest.raises(CdxError):
        handle_conversation(["work2", *selection, "--json"], ctx)
