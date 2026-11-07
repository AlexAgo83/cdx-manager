"""Claude footer rendering uses only the owning profile's local status cache."""

import io
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from src import claude_status_line as line
from src.cli import main
from src.session_service import create_session_service

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


@pytest.fixture
def profile(tmp_path):
    tmp_path = tmp_path / "cdx store with spaces"
    tmp_path.mkdir()
    home = str(tmp_path / "profiles" / "grif" / "claude-home")
    session = {"name": "grif", "provider": "claude", "authHome": home,
               "lastStatus": {"remaining_5h_pct": 25, "remaining_week_pct": 16,
                              "updated_at": NOW.isoformat(), "reset_week_at": "Nov 07 09:30"}}
    def save():
        (tmp_path / "sessions.json").write_text(json.dumps({"sessions": [
            {"name": "other", "provider": "claude", "authHome": str(tmp_path / "other"),
             "lastStatus": {"remaining_5h_pct": 99}}, session]}))
    save()
    return tmp_path, session, save


def test_render_own_home_and_low_window_reset(profile):
    base, session, _ = profile
    with mock.patch("socket.socket", side_effect=AssertionError("network")), \
            mock.patch("subprocess.run", side_effect=AssertionError("provider")):
        assert line.render(base, {"HOME": session["authHome"], "CDX_SESSION_NAME": "other"}, NOW) == (
            "█▁▁▁▁▁▁▁  5h 25% · wk 16% (reset Nov 07 09:30) · grif")
    assert line.render(base, {"CDX_SESSION_NAME": "grif"}, NOW).endswith(" · grif")
    assert line.render(base, {"USERPROFILE": session["authHome"]}, NOW).endswith(" · grif")
    assert line.render(base, {"HOME": "/unrelated", "CDX_SESSION_NAME": "grif"}, NOW) == "quota ?"


@pytest.mark.parametrize("age,stale", [(599, False), (600, True), (601, True), (-1, True)])
def test_cache_freshness_boundary(profile, age, stale):
    base, session, save = profile
    session["lastStatus"]["updated_at"] = (NOW - timedelta(seconds=age)).isoformat()
    save()
    assert line.render(base, {"HOME": session["authHome"]}, NOW).endswith(" · stale") is stale


def test_unknown_and_partial_windows(profile):
    base, session, save = profile
    session["lastStatus"] = {"remaining_5h_pct": 19, "reset_5h_at": "Nov 06 13:00"}
    save()
    assert line.render(base, {"HOME": session["authHome"]}, NOW) == (
        "██▁▁▁▁▁▁  5h 19% (reset Nov 06 13:00) · wk ? · grif · stale")
    session["lastStatus"] = {"remaining_5h_pct": True, "remaining_week_pct": -1}
    save()
    assert line.render(base, {"HOME": session["authHome"]}, NOW) == "quota ?"


@pytest.mark.parametrize("contents", [None, "{", "[]", '{"sessions": {}}', '{"sessions": []}'])
def test_missing_or_malformed_cache_is_silent(tmp_path, contents):
    if contents is not None:
        (tmp_path / "sessions.json").write_text(contents)
    result = subprocess.run([sys.executable, line.__file__, line.MARKER, str(tmp_path)],
                            input='{"context_window": {}}', capture_output=True, text=True, check=True)
    assert result.stdout == "quota ?\n"
    assert result.stderr == ""


@pytest.mark.parametrize("value,expected", [(0, "▁▁▁▁▁▁▁▁"), (6.25, "█▁▁▁▁▁▁▁"),
                                           (62, "█████▁▁▁"), (100, "████████")])
def test_shared_launcher_gauge(value, expected):
    assert line.gauge(value) == expected


def test_created_profile_settings_and_remove_reinstall(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path), "env": {}})
    session = service["create_session"]("grif", "claude")
    path = Path(session["authHome"]) / ".claude/settings.json"
    settings = json.loads(path.read_text())
    assert settings["statusLine"]["type"] == "command"
    assert line.MARKER in settings["statusLine"]["command"]
    settings["custom"] = {"retained": True}
    path.write_text(json.dumps(settings))
    for args, installed in [(["set", "grif", "--status-line", "off"], False),
                            (["set", "grif", "--power", "high"], False),
                            (["unset", "grif", "--status-line"], True),
                            (["set", "grif", "--status-line", "on"], True)]:
        out = io.StringIO()
        assert main([*args, "--json"], {"service": service, "stdout": out}) == 0
        assert ("statusLine" in json.loads(path.read_text())) is installed
        assert json.loads(path.read_text())["custom"] == {"retained": True}
        assert json.loads(out.getvalue())["warnings"] == []
    before = path.stat().st_mtime_ns
    assert line.provision(service["get_session"]("grif"), str(tmp_path)) is None
    assert path.stat().st_mtime_ns == before


@pytest.mark.parametrize("custom", [{"type": "command", "command": "operator-status"}, None, "custom"])
def test_operator_status_line_is_preserved_and_reported(tmp_path, custom):
    service = create_session_service({"base_dir": str(tmp_path), "env": {}})
    session = service["create_session"]("grif", "claude")
    path = Path(session["authHome"]) / ".claude/settings.json"
    original = json.dumps({"statusLine": custom, "permissions": {"allow": []}})
    path.write_text(original)
    for value in ("on", "off"):
        out = io.StringIO()
        assert main(["set", "grif", "--status-line", value, "--json"], {"service": service, "stdout": out}) == 0
        assert json.loads(out.getvalue())["warnings"] == ["grif: operator-defined statusLine preserved"]
        assert path.read_text() == original


def test_invalid_settings_and_codex_are_untouched(tmp_path):
    session = {"provider": "claude", "name": "grif", "authHome": str(tmp_path)}
    directory = tmp_path / ".claude"
    directory.mkdir()
    path = directory / "settings.json"
    path.write_text("{")
    assert "unreadable" in line.provision(session, str(tmp_path))
    assert path.read_text() == "{"
    session["provider"] = "codex"
    assert line.provision(session, str(tmp_path)) is None
    assert path.read_text() == "{"


@pytest.mark.parametrize("output_encoding", ["utf-8", "cp1252", "ascii"])
def test_installed_command_runs_with_spaces(profile, output_encoding):
    base, session, _ = profile
    assert line.provision(session, str(base)) is None
    settings = json.loads((Path(session["authHome"]) / ".claude/settings.json").read_text())
    result = subprocess.run(settings["statusLine"]["command"], shell=True, capture_output=True, text=True, encoding="utf-8",
                            env={**os.environ, "HOME": session["authHome"], "PYTHONIOENCODING": output_encoding}, input="{}", check=True)
    assert result.stdout == line.render(base, {"HOME": session["authHome"]}) + "\n"
    assert result.stderr == ""


def test_window_evidence_does_not_hide_old_quota(profile):
    base, session, save = profile
    session["lastStatus"]["quota_windows"] = {"weekly": {"observed_at": (NOW - timedelta(hours=1)).isoformat()}}
    save()
    assert line.render(base, {"HOME": session["authHome"]}, NOW).endswith(" · stale")


def test_copy_and_rename_resolve_the_destination_profile(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path), "env": {}})
    service["create_session"]("source", "claude")
    session = service["copy_session"]("source", "copied")["session"]
    session = service["rename_session"](session["name"], "renamed")
    from src.session_store import create_session_store

    create_session_store(str(tmp_path))["update_session"]("renamed", lambda s: {**s, "lastStatus": {"remaining_5h_pct": 62, "updated_at": NOW.isoformat()}})
    assert line.render(tmp_path, {"HOME": session["authHome"]}, NOW) == "█████▁▁▁  5h 62% · wk ? · renamed"


def test_programmatic_settings_updates_install_and_remove(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path), "env": {}})
    session = service["create_session"]("grif", "claude")
    path = Path(session["authHome"]) / ".claude/settings.json"
    service["set_launch_settings"]("grif", {"status_line": False})
    assert "statusLine" not in json.loads(path.read_text())
    service["unset_launch_settings"]("grif", ["status_line"])
    assert "statusLine" in json.loads(path.read_text())


def test_cache_ttl_matches_status_service():
    from src.session_status import CLAUDE_STATUS_CACHE_TTL_SECONDS

    assert line.CACHE_TTL_SECONDS == CLAUDE_STATUS_CACHE_TTL_SECONDS


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 10 ** 1000, "16", True, -1, 101])
def test_invalid_quota_is_unknown(value):
    assert line._pct(value) is None


def test_reset_threshold_is_strict(profile):
    base, session, save = profile
    session["lastStatus"].update(remaining_5h_pct=20, remaining_week_pct=89, reset_5h_at="Nov 06 13:00")
    save()
    assert line.render(base, {"HOME": session["authHome"]}, NOW) == "██▁▁▁▁▁▁  5h 20% · wk 89% · grif"
