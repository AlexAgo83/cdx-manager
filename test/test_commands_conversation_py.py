"""Conversation CLI parsing and JSON envelope contracts."""

import io
import json
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
