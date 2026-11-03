"""Synthetic native payloads, with no provider credentials or network calls."""

import base64
import io
import json
import os
import shlex
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from src import antigravity_status as ag
from src.commands.runs import _observe_headless_usage
from src.provider_runtime import _build_headless_launch_spec, _build_launch_spec
from src.run_usage import coerce_usage, extract_run_usage
from src.session_status import _status_row_from_session
from src.status_view import _format_status_detail, _format_status_rows

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def payload():
    return {"plan_tier": "pro", "email": "private@example.invalid", "cwd": "/private",
            "transcript_path": "/private/log", "token": "secret", "session_id": "private-session",
            "quota": {name: {"remaining_fraction": fraction, "reset_time": "2026-11-09T13:24:17Z",
                             "reset_in_seconds": 567324, "token": "secret"}
                      for name, fraction in (("gemini-5h", .75), ("gemini-weekly", .9830272),
                                             ("3p-weekly", .968621), ("3p-5h", .8), ("new-bucket", .42))}}


def state_path(home):
    return home / ".gemini" / "antigravity-cli" / ag.STATE_NAME


def test_capture_is_private_and_allowlisted(tmp_path):
    path = state_path(tmp_path)
    ag.capture(payload(), path, NOW)
    document = json.loads(path.read_text())
    assert set(document) == {"time", "plan_tier", "quota"}
    assert set(document["quota"]["new-bucket"]) == {"remaining_fraction", "reset_time", "reset_in_seconds"}
    assert "secret" not in path.read_text()
    assert "private" not in path.read_text()
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        path.chmod(0o644)
        ag.capture(payload(), path, NOW)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.iterdir()) == [path]


def test_all_buckets_and_gemini_windows(tmp_path):
    ag.capture(payload(), state_path(tmp_path), NOW)
    reading = ag.read_status(tmp_path, NOW + timedelta(seconds=90))
    assert reading["remaining_5h_pct"] == 75
    assert reading["remaining_week_pct"] == pytest.approx(98.30272)
    assert reading["quota"]["3p-weekly"]["remaining_fraction"] == .968621
    assert reading["quota"]["new-bucket"]["remaining_fraction"] == .42
    assert reading["reading_age_seconds"] == 90
    assert reading["reset_week_at_iso"] == "2026-11-09T13:24:17+00:00"
    assert reading["plan_tier"] == "pro"


@pytest.mark.parametrize("quota", [None, {}, [], {"new": {"remaining_fraction": .4}}])
def test_missing_quota_or_gemini_buckets_stays_unknown(tmp_path, quota):
    ag.capture({"quota": quota}, state_path(tmp_path), NOW)
    reading = ag.read_status(tmp_path, NOW)
    assert reading["remaining_5h_pct"] is None
    assert reading["remaining_week_pct"] is None


@pytest.mark.parametrize("age,stale", [(86400, False), (86401, True)])
def test_staleness_boundary(tmp_path, age, stale):
    ag.capture(payload(), state_path(tmp_path), NOW)
    reading = ag.read_status(tmp_path, NOW + timedelta(seconds=age))
    assert reading["quota_stale"] is stale
    assert (reading["remaining_week_pct"] is None) is stale
    assert reading["quota_status"] == ("stale" if stale else "current")
    if stale:
        assert reading["quota"]["3p-weekly"]["status"] == "stale"
        assert reading["quota"]["3p-weekly"]["remaining_fraction"] is None


def test_past_reset_is_unknown_for_every_bucket(tmp_path):
    document = payload()
    for bucket in document["quota"].values():
        bucket["reset_time"] = "2026-11-02T12:00:00Z"
    ag.capture(document, state_path(tmp_path), NOW)
    reading = ag.read_status(tmp_path, NOW)
    assert reading["remaining_week_pct"] is None
    assert reading["reset_week_at"] is None
    assert reading["quota"]["3p-weekly"]["status"] == "unknown"
    assert reading["quota"]["new-bucket"]["remaining_fraction"] is None


def test_settings_merge_and_existing_output(tmp_path):
    settings = state_path(tmp_path).with_name("settings.json")
    settings.parent.mkdir(parents=True)
    previous = 'python3 -c "import sys; print(sys.stdin.read(), end=\'\')"'
    original = {"theme": "dark", "nested": {"keep": [1, 2]},
                "statusLine": {"type": "command", "command": previous, "padding": 2}}
    settings.write_text(json.dumps(original))
    assert ag.install(str(tmp_path))
    installed = json.loads(settings.read_text())
    assert installed["theme"] == "dark"
    assert installed["nested"] == original["nested"]
    assert installed["statusLine"]["padding"] == 2
    assert ag.install(str(tmp_path))
    assert json.loads(settings.read_text()) == installed
    # Feed real stdin through the installed command and its existing command.
    raw = json.dumps(payload())
    result = subprocess.run(installed["statusLine"]["command"], shell=True, input=raw,
                            capture_output=True, text=True, check=True)
    assert result.stdout == raw
    assert result.stderr == ""
    assert json.loads(state_path(tmp_path).read_text())["quota"]["3p-weekly"]


def test_invalid_settings_are_preserved(tmp_path):
    settings = state_path(tmp_path).with_name("settings.json")
    settings.parent.mkdir(parents=True)
    settings.write_text("invalid settings")
    assert not ag.install(str(tmp_path))
    assert settings.read_text() == "invalid settings"


def test_capture_failure_still_runs_previous_command(tmp_path):
    previous = base64.urlsafe_b64encode(b"echo preserved").decode()
    with mock.patch.object(ag.sys, "argv", ["hook", "--state", str(tmp_path / "state"), "--previous", previous]), \
            mock.patch.object(ag.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
        assert ag.main(io.StringIO("invalid")) == 0
        assert run.call_args.kwargs["input"] == "invalid"


def test_status_rows_refresh_locally_even_with_old_cached_status(tmp_path):
    ag.capture(payload(), state_path(tmp_path), NOW)
    session = {"name": "agy", "provider": "antigravity", "authHome": str(tmp_path),
               "lastStatus": {"remaining_week_pct": 100}, "lastStatusAt": NOW.isoformat()}
    with mock.patch("src.session_status._session_runtime", return_value=None), \
            mock.patch.object(ag, "datetime") as clock:
        clock.now.return_value = NOW + timedelta(days=2)
        clock.fromisoformat = datetime.fromisoformat
        row = _status_row_from_session({}, session)
    assert row["remaining_week_pct"] is None
    assert row["available_pct"] is None
    assert row["status"] == "stale"
    assert row["reading_age_seconds"] == 172800
    assert "stale" in _format_status_rows([row])
    assert "Plan: pro" in _format_status_detail(row)


def test_launch_installs_hook_and_headless_uses_print_json(tmp_path):
    session = {"name": "agy", "provider": "antigravity", "authHome": str(tmp_path)}
    spec = _build_launch_spec(session, capture_transcript=False)
    assert spec["command"] == "agy"
    assert state_path(tmp_path).with_name("settings.json").is_file()
    spec = _build_headless_launch_spec(session, initial_prompt="hello")
    assert spec["args"][:4] == ["-p", "hello", "--output-format", "json"]
    assert spec["options"]["env"]["HOME"] == str(tmp_path)
    assert "--prompt-interactive" not in spec["args"]
    if os.name != "nt":
        command = json.loads(state_path(tmp_path).with_name("settings.json").read_text())["statusLine"]["command"]
        assert ag.MARKER in shlex.split(command)


def test_headless_usage_survives_observation_and_registry_normalization(tmp_path):
    path = tmp_path / "stdout.json"
    path.write_text(json.dumps({"model": "gemini-model", "usage": {
        "input_tokens": 100, "output_tokens": 20, "thinking_tokens": 7,
        "cache_read_tokens": 40, "total_tokens": 127}}))
    usage = extract_run_usage("antigravity", path)
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 20
    assert usage["reasoning_tokens"] == 7
    assert usage["cache_read_tokens"] == 40
    assert usage["total_tokens"] == 127
    observed = _observe_headless_usage({"provider": "antigravity"}, {"stdout_path": path})
    assert observed["usage"] == usage
    assert observed["usage_model"] == "gemini-model"
    assert coerce_usage(usage, provider="antigravity") == usage


def test_unrelated_command_containing_marker_is_preserved(tmp_path):
    settings = state_path(tmp_path).with_name("settings.json")
    settings.parent.mkdir(parents=True)
    previous = "echo " + ag.MARKER
    settings.write_text(json.dumps({"statusLine": {"type": "command", "command": previous}}))
    assert ag.install(str(tmp_path))
    command = json.loads(settings.read_text())["statusLine"]["command"]
    assert base64.urlsafe_b64encode(previous.encode()).decode() in command


def test_fresh_status_row_uses_gemini_and_native_reset(tmp_path):
    ag.capture(payload(), state_path(tmp_path), NOW)
    session = {"name": "agy", "provider": "antigravity", "authHome": str(tmp_path)}
    with mock.patch("src.session_status._session_runtime", return_value=None), \
            mock.patch.object(ag, "datetime") as clock:
        clock.now.return_value = NOW
        clock.fromisoformat = datetime.fromisoformat
        row = _status_row_from_session({}, session)
    assert row["remaining_5h_pct"] == 75
    assert row["remaining_week_pct"] == 98
    assert row["reset_week_at_iso"] == "2026-11-09T13:24:17+00:00"
    assert row["updated_at"] == NOW.isoformat()
    table = _format_status_rows([row])
    assert "75%" in table and "98%" in table
    assert row["quota"]["3p-weekly"]["remaining_fraction"] == .968621
