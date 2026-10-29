"""Historical serving-model recovery must never guess from live settings."""

import json
from pathlib import Path
from unittest import mock

import pytest

from src.commands.status import _stats_group, _summarize_stats, handle_history
from src.errors import CdxError
from src.history_models import recover_model
from src.run_usage import normalize_usage
from src.session_service import create_session_service

THREAD = "12345678-1234-1234-1234-123456789abc"
MODEL = "claude-opus-5-5"


@pytest.fixture
def write_records(tmp_path):
    def write(name, records):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        return str(path)
    return write


@pytest.fixture
def history(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path), "env": {}})
    service["create_session"]("work", provider="claude")
    entry = {"status": "success", "started_at": "2026-01-01T12:00:00Z", "run_id": "run-1",
             "usage": normalize_usage(input_tokens=100, output_tokens=10)}
    return service, entry, tmp_path / "state" / "launch_history.jsonl"


def assistant(model):
    return {"type": "assistant", "message": {"model": model, "usage": {"input_tokens": 100}}}


def test_stdout_dry_run_apply_backup_and_stats(history, write_records):
    service, entry, path = history
    entry["stdout_path"] = write_records("stdout.jsonl", [assistant(MODEL)])
    service["record_launch_history"]("work", entry)
    # Unrelated bytes, including malformed rows and blank lines, survive exactly.
    with path.open("ab") as handle:
        handle.write(b"\nnot-json\n[]\n")
    original = path.read_bytes()
    preview = service["backfill_history_models"]()
    assert preview["recoverable"]["stdout"] == 1
    assert preview["backfilled"] == 0
    assert path.read_bytes() == original
    assert not list(path.parent.glob("*.bak"))
    result = service["backfill_history_models"](dry_run=False)
    assert result["backfilled"] == 1
    assert Path(result["backup_path"]).read_bytes() == original
    assert path.read_bytes().endswith(b"\nnot-json\n[]\n")
    recovered = json.loads(path.read_text().splitlines()[0])
    assert recovered["usage"] == entry["usage"]
    assert recovered["usage_model"] == MODEL
    assert recovered["usage_model_backfilled_reason"] == "stdout"
    assert _summarize_stats([recovered])[0]["priced_runs"] == 1
    assert service["backfill_history_models"](dry_run=False)["backfilled"] == 0
    assert len(list(path.parent.glob("*.bak"))) == 1


def test_run_report_uses_observed_model_only(history, write_records, tmp_path):
    service, entry, _path = history
    entry["stdout_path"] = str(tmp_path / "removed.stdout")
    report = {"run_id": "run-1", "session": "work", "provider": "claude",
              "model": "configured-model", "usage_model": MODEL,
              "artifacts": {"stdout_path": entry["stdout_path"]}}
    write_records("runs.json", [{"runs": [report]}])
    service["record_launch_history"]("work", entry)
    assert service["backfill_history_models"]()["recoverable"]["run_report"] == 1
    for change in ({"usage_model": None}, {"session": "other"}, {"provider": "codex"},
                   {"run_id": "other"}, {"artifacts": {"stdout_path": "other-attempt"}}):
        write_records("runs.json", [{"runs": [{**report, **change}]}])
        assert service["backfill_history_models"]()["still_unknown"] == 1


def test_codex_exact_thread_rollout(write_records, tmp_path):
    stdout = write_records("codex.stdout", [{"type": "thread.started", "thread_id": THREAD},
                                            {"type": "turn.completed", "usage": {"input_tokens": 100}}])
    write_records(f"sessions/2026/rollout-date-{THREAD}.jsonl",
                  [{"type": "turn_context", "payload": {"model": "gpt-5"}}])
    assert recover_model({"provider": "codex", "stdout_path": stdout}, {"authHome": str(tmp_path)}) == (
        "gpt-5", "codex_rollout", None)
    assert recover_model({"provider": "codex", "thread_id": "absent"}, {"authHome": str(tmp_path)})[2] == "exact_transcript_missing"


def test_claude_exact_session_transcript(write_records, tmp_path):
    write_records(".claude/projects/project/session-1.jsonl", [assistant(MODEL), assistant(MODEL + "[1m]")])
    result = recover_model({"provider": "claude", "session_id": "session-1"}, {"authHome": str(tmp_path)})
    assert result == (MODEL, "claude_transcript", None)
    transcript = write_records("preserved/session-1.jsonl", [assistant(MODEL + "[1m]")])
    entry = {"provider": "claude", "provider_transcript_path": transcript, "provider_transcript_match": "conversation_id"}
    assert recover_model(entry)[0] == MODEL + "[1m]"
    assert _stats_group({"usage_model": recover_model(entry)[0]}, "model") == MODEL
    entry["provider_transcript_match"] = "recency"
    assert recover_model(entry)[2] == "no_run_conversation_id"


@pytest.mark.parametrize("kind", ["stdout", "claude_transcript", "codex_rollout"])
def test_mixed_models_are_unknown_even_with_configured_default(kind, write_records):
    if kind == "codex_rollout":
        records = [{"type": "turn_context", "payload": {"model": model}} for model in ("gpt-5", "gpt-4.1")]
        name = f"rollout-date-{THREAD}.jsonl"
        entry = {"provider": "codex", "thread_id": THREAD}
    else:
        records = [assistant(MODEL), assistant("claude-sonnet-5-5")]
        name = "session-1.jsonl"
        entry = {"provider": "claude", "session_id": "session-1"}
    path = write_records(name, records)
    entry["stdout_path" if kind == "stdout" else "provider_transcript_path"] = path
    assert recover_model(entry, {"launch": {"model": MODEL}})[2] == "ambiguous_models"


def test_no_fallback_to_latest_transcript_or_profile_conversation(write_records, tmp_path):
    write_records(".claude/projects/project/latest.jsonl", [assistant(MODEL)])
    session = {"authHome": str(tmp_path), "conversation": {"id": "latest"}, "launch": {"model": MODEL}}
    assert recover_model({"provider": "claude"}, session)[2] == "no_run_conversation_id"
    assert recover_model({"provider": "claude", "session_id": "missing"}, session)[2] == "exact_transcript_missing"
    assert recover_model({"provider": "claude", "model": MODEL, "launch": {"model": MODEL}}, session)[0] is None


def test_incomplete_or_corrupt_evidence_is_unknown(write_records):
    path = write_records("stdout", [assistant(MODEL), assistant(None)])
    assert recover_model({"provider": "claude", "stdout_path": path})[2] == "incomplete_model_evidence"
    with open(path, "a") as handle:
        handle.write('{"truncated":')
    assert recover_model({"provider": "claude", "stdout_path": path})[2] == "unreadable_evidence"


def test_identity_conflicts_are_unknown(write_records):
    path = write_records("stdout", [{"type": "thread.started", "thread_id": THREAD}])
    assert recover_model({"provider": "codex", "stdout_path": path, "thread_id": "other"})[2] == "ambiguous_conversation_ids"
    assert recover_model({"provider": "claude", "session_id": "one", "provider_transcript_path": "two.jsonl"})[2] == "transcript_identity_mismatch"


def test_existing_models_and_missing_usage_are_untouched(history):
    service, entry, path = history
    service["record_launch_history"]("work", {**entry, "usage_model": MODEL})
    service["record_launch_history"]("work", {**entry, "usage": None})
    original = path.read_bytes()
    assert service["backfill_history_models"](dry_run=False)["candidates"] == 0
    assert path.read_bytes() == original


def test_backup_failure_leaves_history_untouched(history, write_records):
    service, entry, path = history
    service["record_launch_history"]("work", {**entry, "stdout_path": write_records("stdout", [assistant(MODEL)])})
    original = path.read_bytes()
    with mock.patch("src.session_store.atomic_write", side_effect=OSError("disk full")), pytest.raises(OSError):
        service["backfill_history_models"](dry_run=False)
    assert path.read_bytes() == original


def test_rewrite_failure_keeps_backup_and_history(history, write_records):
    from src.fs_utils import atomic_write

    service, entry, path = history
    service["record_launch_history"]("work", {**entry, "stdout_path": write_records("stdout", [assistant(MODEL)])})
    original = path.read_bytes()
    def fail_rewrite(target, data):
        if target == str(path):
            raise OSError("disk full")
        atomic_write(target, data)
    with mock.patch("src.session_store.atomic_write", side_effect=fail_rewrite), pytest.raises(OSError):
        service["backfill_history_models"](dry_run=False)
    assert path.read_bytes() == original
    assert next(path.parent.glob("*.bak")).read_bytes() == original


def test_command_defaults_output_and_invalid_flags(history, write_records):
    service, entry, _path = history
    service["record_launch_history"]("work", {**entry, "stdout_path": write_records("stdout", [assistant(MODEL)])})
    output = []
    ctx = {"service": service, "out": output.append}
    assert handle_history(["backfill-models"], ctx) == 0
    assert "Dry run" in "".join(output)
    assert "Recoverable from stdout: 1" in "".join(output)
    assert service["get_launch_history"]()[0].get("usage_model") is None
    for args in (["--apply", "--dry-run"], ["--limit", "1"], ["unexpected"]):
        with pytest.raises(CdxError):
            handle_history(["backfill-models", *args], ctx)


def test_multiple_exact_transcripts_and_internal_identity_conflicts(write_records, tmp_path):
    for project in ("one", "two"):
        write_records(f".claude/projects/{project}/session-1.jsonl", [assistant(MODEL)])
    entry = {"provider": "claude", "session_id": "session-1"}
    assert recover_model(entry, {"authHome": str(tmp_path)})[2] == "multiple_exact_transcripts"
    path = write_records("session-1.jsonl", [{**assistant(MODEL), "sessionId": "other"}])
    assert recover_model({**entry, "provider_transcript_path": path})[2] == "transcript_identity_mismatch"
    path = write_records("other-session-1.jsonl", [assistant(MODEL)])
    assert recover_model({**entry, "provider_transcript_path": path})[2] == "transcript_identity_mismatch"


def test_each_row_needs_its_own_evidence_even_with_same_profile_and_start(history, write_records):
    service, entry, path = history
    for model in (MODEL, "claude-sonnet-5-5"):
        stdout = write_records(model, [assistant(model)])
        service["record_launch_history"]("work", {**entry, "stdout_path": stdout, "usage_model": None})
    service["record_launch_history"]("work", {**entry, "usage_model": None})
    result = service["backfill_history_models"](dry_run=False)
    assert result["backfilled"] == 2
    assert result["still_unknown"] == 1
    assert result["unknown_reasons"] == {"no_run_conversation_id": 1}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["usage_model"] for row in rows] == [MODEL, "claude-sonnet-5-5", None]


def test_ambiguous_stdout_is_not_overridden_by_report(write_records):
    path = write_records("stdout", [assistant(MODEL), assistant("claude-sonnet-5-5")])
    entry = {"provider": "claude", "session_name": "work", "run_id": "r", "stdout_path": path}
    report = {"provider": "claude", "session": "work", "run_id": "r", "usage_model": MODEL,
              "artifacts": {"stdout_path": path}}
    assert recover_model(entry, reports=[report]) == (None, "stdout", "ambiguous_models")


def test_conflicting_reports_are_unknown():
    entry = {"provider": "claude", "session_name": "work", "run_id": "r", "stdout_path": "/missing-stdout"}
    report = {"provider": "claude", "session": "work", "run_id": "r", "usage_model": MODEL,
              "artifacts": {"stdout_path": "/missing-stdout"}}
    assert recover_model(entry, reports=[report, {**report, "usage_model": "claude-sonnet-5-5"}])[2] == "ambiguous_models"


def test_missing_history_does_not_create_backup(history):
    service, _entry, path = history
    result = service["backfill_history_models"](dry_run=False)
    assert result["scanned"] == 0
    assert result["backup_path"] is None
    assert not path.exists()


def test_preserved_cdx_output_never_uses_requested_model(write_records):
    report = {"action": "run", "launcher": "cdx", "run_id": "r", "session": "work", "provider": "claude",
              "model": MODEL, "usage": {"input_tokens": 100}, "usage_model": None}
    entry = {"run_id": "r", "session_name": "work", "provider": "claude"}
    path = write_records("stdout", [report])
    assert recover_model({**entry, "stdout_path": path})[0] is None
    write_records("stdout", [{**report, "usage_model": "claude-sonnet-5-5"}])
    assert recover_model({**entry, "stdout_path": path})[0] == "claude-sonnet-5-5"
    assert recover_model({**entry, "run_id": "other", "stdout_path": path})[2] == "report_identity_mismatch"
