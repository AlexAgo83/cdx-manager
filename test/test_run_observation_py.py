"""Exact-attempt observation exports contain accounting evidence only."""

import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from src.history_models import recover_model
from src.run_observation import codex_attempt_evidence
from src.run_usage import cost_fields, extract_run_observation

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Isolated observation is Linux-only")


@pytest.mark.parametrize("models,reason", [(["gpt-6.1-sol"], None), ([], "model_not_observed"),
                                          (["new-model"], "model_price_unknown"),
                                          (["gpt-6.1-sol", "gpt-6-sol"], "mixed_models_without_counters")])
def test_minimal_export_and_recovery(tmp_path, models, reason):
    start = datetime.now(timezone.utc) - timedelta(seconds=2)
    timestamp = (start + timedelta(seconds=1)).isoformat()
    stdout = tmp_path / "stdout.jsonl"
    counters = {"input_tokens": 100, "cached_input_tokens": 60, "cache_write_input_tokens": 10,
                "output_tokens": 20, "reasoning_output_tokens": 5}
    stdout.write_text(json.dumps({"type": "thread.started", "thread_id": "11111111-1111-4111-8111-111111111111"}) + "\n" +
                      json.dumps({"type": "turn.completed", "usage": counters}) + "\n")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    rollout = sessions / "rollout-2026-11111111-1111-4111-8111-111111111111.jsonl"
    records = [{"type": "session_meta", "payload": {"id": "11111111-1111-4111-8111-111111111111"}},
               {"type": "response_item", "payload": {"text": "PRIVATE CONVERSATION"}},
               *[{"type": "turn_context", "timestamp": timestamp,
                  "payload": {"model": model, "turn_id": {"text": "PRIVATE ID CONTENT"} if index == 0 else str(index), "prompt": "PRIVATE PROMPT"}}
                 for index, model in enumerate(models)],
               {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": counters}}}]
    rollout.write_text("\n".join(map(json.dumps, records)))
    evidence = codex_attempt_evidence(tmp_path, stdout, start.isoformat())
    usage, model = extract_run_observation("codex", stdout, evidence=evidence)
    assert usage["input_tokens"] == 30
    assert usage["cache_read_tokens"] == 60
    assert usage["cache_creation_tokens"] == 10
    assert usage["total_tokens"] == 120
    assert cost_fields(usage, model, models=evidence["models"])["cost_reason"] == reason
    assert "PRIVATE" not in json.dumps(evidence)
    entry = {"provider": "codex", "stdout_path": str(stdout), "usage": usage, "usage_evidence": evidence}
    recovered, kind, _ = recover_model(entry)
    assert recovered == model
    assert kind == "isolated_observation"
    # Live provider-native counters are measured before exec emits its final usage.
    completed_stdout = stdout.read_text()
    stdout.write_text(json.dumps({"type": "thread.started", "thread_id": "11111111-1111-4111-8111-111111111111"}) + "\n")
    live_evidence = codex_attempt_evidence(tmp_path, stdout, start.isoformat())
    live_usage, live_model = extract_run_observation("codex", stdout, evidence=live_evidence)
    assert live_usage == usage
    assert live_model == model
    stdout.write_text(completed_stdout)
    # Another attempt with the same logical run/thread must not inherit this evidence.
    another = tmp_path / "other-stdout.jsonl"
    another.write_text(stdout.read_text())
    assert extract_run_observation("codex", another, evidence=evidence)[1] is None
    entry["stdout_path"] = str(another)
    assert recover_model(entry)[2] == "observation_attempt_mismatch"
    # A context predating this attempt cannot establish the serving model.
    assert not codex_attempt_evidence(tmp_path, stdout, datetime.now(timezone.utc).isoformat())["models"]
    # Counter disagreement and symlink evidence are rejected.
    records[-1]["payload"]["info"]["total_token_usage"] = {"input_tokens": 1}
    rollout.write_text("\n".join(map(json.dumps, records)))
    assert not codex_attempt_evidence(tmp_path, stdout, start.isoformat())["models"]
    saved = tmp_path / "saved"
    rollout.rename(saved)
    rollout.symlink_to(saved)
    assert not codex_attempt_evidence(tmp_path, stdout, start.isoformat())["models"]


@pytest.mark.parametrize("failure", [RuntimeError("startup failed"), KeyboardInterrupt()])
def test_volatile_attempt_storage_is_removed_on_failure(monkeypatch, failure):
    from src import provider_runtime

    mounted = []

    def attempt(*args, **kwargs):
        directory = args[8]
        mounted.append(directory)
        with open(f"{directory}/sessions/private.jsonl", "w") as handle:
            handle.write("PRIVATE")
        raise failure

    from test_remote_run_py import credential

    from src import remote_run
    monkeypatch.setattr(remote_run, 'remote_auth_lock', lambda *_: __import__('contextlib').nullcontext())
    monkeypatch.setattr(remote_run, 'temporary_auth', lambda *_: {**credential(), 'tokens': {**credential()['tokens'], 'refresh_token': ''}})
    monkeypatch.setattr(provider_runtime, "_run_headless_provider_attempt", attempt)
    from src.errors import CdxError
    with pytest.raises(CdxError):
        provider_runtime._run_headless_provider_command({"provider": "codex", "authHome": "/profile", "launch": {"isolate_workspace": True}})
    import os

    assert not os.path.exists(mounted[0])
