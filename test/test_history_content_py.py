"""Interactive history identity and clean prompt regression coverage."""

import json

import pytest

from src.history_content import enrich_history, first_user_prompt


def write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return str(path)


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_first_real_user_prompt_skips_wrappers_and_paths(tmp_path, provider):
    texts = ["<local-command-caveat>Ignore these local messages.</local-command-caveat>",
             "<command-name>/clear</command-name><command-message>clear</command-message>",
             "<system-reminder>Injected context</system-reminder>", "/home/user/project/README.md",
             "README.md", "./docs/cli.md",
             "<system-reminder>Context</system-reminder>\nFix the resume dialog."]
    records = [{"type": "user", "message": {"role": "user", "content": text}} for text in texts]
    if provider == "codex":
        records = [{"type": "response_item", "payload": record["message"]} for record in records]
    path = write_records(tmp_path / "transcript.jsonl", [
        {"type": "assistant", "message": {"content": "Not a prompt"}}, *records])
    assert first_user_prompt(provider, path) == "Fix the resume dialog."


def test_claude_exact_id_wins_over_newer_unrelated_transcript(tmp_path):
    identifier = "12345678-1234-1234-1234-123456789abc"
    path = write_records(tmp_path / ".claude/projects/repo" / f"{identifier}.jsonl", [
        {"type": "user", "message": {"content": "Continue the repair"}}])
    write_records(tmp_path / ".claude/projects/repo/unrelated.jsonl", [
        {"type": "user", "message": {"content": "Wrong conversation"}}])
    row = enrich_history({"conversation_id": identifier}, {"provider": "claude", "authHome": str(tmp_path)})
    assert row["provider_transcript_path"] == path
    assert row["provider_transcript_match"] == "conversation_id"
    assert row["first_user_prompt"] == "Continue the repair"


def test_legacy_claude_identity_is_recovered_from_launch_args(tmp_path):
    identifier = "12345678-1234-1234-1234-123456789abc"
    write_records(tmp_path / ".claude/projects/repo" / f"{identifier}.jsonl", [])
    row = enrich_history({"args": ["-c", f"claude --session-id {identifier}"]},
                         {"provider": "claude", "authHome": str(tmp_path)})
    assert row["conversation_id"] == identifier
    assert row["provider_transcript_match"] == "conversation_id"


@pytest.mark.parametrize("ambiguous", [False, True])
def test_codex_identity_requires_unique_metadata_in_launch_scope(tmp_path, ambiguous):
    identifiers = ["12345678-1234-1234-1234-123456789abc", "abcdefab-1234-1234-1234-123456789abc"]
    for index, identifier in enumerate(identifiers):
        write_records(tmp_path / "sessions" / f"rollout-2026-11-04-{identifier}.jsonl", [
            {"type": "session_meta", "timestamp": "2026-11-04T10:01:00Z",
             "payload": {"id": identifier, "cwd": str(tmp_path if index == 0 or ambiguous else tmp_path / "other")}}])
    row = enrich_history({"cwd": str(tmp_path), "started_at": "2026-11-04T10:00:00Z",
                          "ended_at": "2026-11-04T10:02:00Z"},
                         {"provider": "codex", "authHome": str(tmp_path)})
    if ambiguous:
        assert not row.get("conversation_id")
        assert row["provider_transcript_match"] == "recency"
    else:
        assert row["conversation_id"] == identifiers[0]
        assert row["provider_transcript_match"] == "conversation_id"


def test_missing_exact_transcript_never_borrows_another_prompt(tmp_path):
    write_records(tmp_path / ".claude/projects/repo/other.jsonl", [
        {"type": "user", "message": {"content": "Wrong prompt"}}])
    row = enrich_history({"conversation_id": "missing"}, {"provider": "claude", "authHome": str(tmp_path)})
    assert "first_user_prompt" not in row
    assert "provider_transcript_path" not in row


def test_prompt_reader_is_bounded_and_ignores_tool_results(tmp_path):
    path = write_records(tmp_path / "transcript.jsonl", [
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "Not user text"}]}},
        {"type": "user", "message": {"content": [{"type": "text", "text": "Actual request"}]}}])
    assert first_user_prompt("claude", path) == "Actual request"
    with open(path, "wb") as handle:
        handle.write(b"x" * (1024 * 1024 + 1))
    assert first_user_prompt("claude", path) is None


def test_prompt_text_cannot_supply_a_launch_identity(tmp_path):
    row = enrich_history({"args": ["-c", "claude 'please use --resume 12345678-1234-1234-1234-123456789abc'"]},
                         {"provider": "claude", "authHome": str(tmp_path)})
    assert not row.get("conversation_id")


def test_initial_prompt_fallback_is_cleaned_and_redacted(tmp_path):
    row = enrich_history({"first_user_prompt": "<system-reminder>Context</system-reminder>\nUse password=fake-value carefully"},
                         {"provider": "claude", "authHome": str(tmp_path)})
    assert row["first_user_prompt"] == "Use [REDACTED] carefully"
