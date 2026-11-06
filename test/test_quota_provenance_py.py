"""Quota evidence remains local to each profile and each measured window."""

import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from src.claude_usage import fetch_claude_rate_limit_headers
from src.cli import main
from src.codex_usage import normalize_codex_rate_limit_snapshot
from src.quota_provenance import quota_windows
from src.session_service import create_session_service
from src.session_status import _merge_status_payload


@pytest.fixture(autouse=True)
def disable_update_checks(monkeypatch):
    monkeypatch.setenv("CDX_DISABLE_UPDATE_CHECK", "1")


def test_status_json_preserves_profile_observation_ages(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path)})
    now = datetime.now(timezone.utc)
    for name, age in (("fresh", 10), ("old", 301)):
        service["create_session"](name, "codex")
        service["record_status"](name, {
            "remaining_5h_pct": 75,
            "updated_at": (now - timedelta(seconds=age)).isoformat(),
            "source_ref": "api:codex-app-server-rate-limits",
            "reset_5h_at": "Nov 7 12:00",
        })
    stdout = io.StringIO()
    assert main(["status", "--cached", "--json"], {"service": service, "stdout": stdout, "stderr": io.StringIO()}) == 0
    rows = {row["session_name"]: row for row in json.loads(stdout.getvalue())["rows"]}
    for name, availability in (("fresh", "measured"), ("old", "stale")):
        row = rows[name]
        assert row["quota_windows"]["5h"] == {
            "source": "codex_rate_limits", "observed_at": row["updated_at"],
            "availability": availability, "reason": None,
        }
        assert row["remaining_week_pct"] is None
        assert row["quota_windows"]["weekly"] == {
            "source": "unknown", "observed_at": None, "availability": "unavailable", "reason": "missing_window",
        }
        assert row["reset_5h_at"] == "Nov 7 12:00"
        assert row["reset_5h_at_iso"].startswith("2026-11-07T12:00")
    assert rows["fresh"]["updated_at"] != rows["old"]["updated_at"]


def test_codex_measurement_source_missing_window_and_reset():
    status = normalize_codex_rate_limit_snapshot({
        "primary": {"windowDurationMins": 300, "usedPercent": 25, "resetsAt": 1794052800},
    })
    assert status["remaining_5h_pct"] == 75
    assert status["remaining_week_pct"] is None
    assert status["quota_windows"]["5h"]["source"] == "codex_rate_limits"
    assert status["quota_windows"]["weekly"]["source"] == "unknown"
    assert status["reset_5h_at"] is not None


@pytest.mark.parametrize("failure,reason", [
    ({"response": {"error": {"message": "authentication token is expired"}}}, "login_expired"),
    ({"reason": "rate_limits_read_failed"}, "rate_limits_read_failed"),
])
def test_codex_failure_keeps_cached_measurement_unavailable(tmp_path, failure, reason):
    service = create_session_service({"base_dir": str(tmp_path)})
    service["create_session"]("work", "codex")
    measured_at = "2026-11-01T10:00:00+00:00"
    service["record_status"]("work", {"remaining_5h_pct": 45, "updated_at": measured_at})
    with mock.patch("src.codex_usage.fetch_codex_rate_limit_diagnostic", return_value={"ok": False, **failure}) as probe:
        row = service["get_status_row"]("work", force_refresh=True)
    assert probe.call_count == 1
    assert row["remaining_5h_pct"] == 45
    assert row["quota_windows"]["5h"]["observed_at"] == measured_at
    assert row["quota_windows"]["5h"]["availability"] == "unavailable"
    assert row["quota_windows"]["5h"]["reason"] == reason


def test_claude_probe_source_and_reset():
    response = mock.MagicMock()
    response.__enter__.return_value.getheaders.return_value = [
        ("anthropic-ratelimit-unified-5h-utilization", "0.25"),
        ("anthropic-ratelimit-unified-5h-reset", "1794052800"),
    ]
    with mock.patch("urllib.request.urlopen", return_value=response) as probe:
        status = fetch_claude_rate_limit_headers("fake-access")
    assert probe.call_count == 1
    assert status["quota_windows"]["5h"]["source"] == "claude_probe"
    assert status["quota_windows"]["5h"]["availability"] == "measured"
    assert status["remaining_week_pct"] is None
    assert status["reset_5h_at"] is not None


@pytest.mark.parametrize("expired", [False, True])
def test_claude_status_json_reports_expired_login_and_network_failure(tmp_path, expired):
    service = create_session_service({"base_dir": str(tmp_path)})
    service["create_session"]("work", "claude")
    stdout = io.StringIO()
    with mock.patch("src.commands.status._refresh_claude_auth_states", return_value={"errors": [], "probed": {"work"}}), \
         mock.patch("src.claude_usage._read_claude_credentials", return_value={"accessToken": "fake-access"}), \
         mock.patch("src.claude_usage._access_token_expired", return_value=expired), \
         mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")) as probe:
        assert main(["status", "work", "--refresh", "--json"], {
            "service": service, "stdout": stdout, "stderr": io.StringIO(),
        }) == 0
    row = json.loads(stdout.getvalue())["session"]
    assert row["remaining_5h_pct"] is None
    for window in row["quota_windows"].values():
        assert window["availability"] == "unavailable"
        assert window["reason"] == ("login_expired" if expired else "quota_read_failed")
        assert window["observed_at"] is None
    assert probe.call_count == (0 if expired else 1)


def test_claude_statusline_cache_unknown_time_and_threshold():
    now = datetime.now(timezone.utc)
    for source_ref, source in (("claude:statusline", "claude_statusline"), ("legacy", "cache")):
        status = {"remaining_5h_pct": 0, "source_ref": source_ref, "updated_at": (now - timedelta(seconds=600)).isoformat()}
        window = quota_windows(status, "claude", now=now)["5h"]
        assert window["source"] == source
        assert window["availability"] == "stale"
        status["updated_at"] = "invalid"
        assert quota_windows(status, "claude")["5h"]["observed_at"] is None


def test_backfilled_window_retains_its_own_evidence():
    current = {"remaining_5h_pct": 90, "updated_at": "2026-11-06T10:00:00+00:00"}
    older = {"remaining_week_pct": 50, "updated_at": "2026-11-01T10:00:00+00:00"}
    merged = _merge_status_payload(current, older)
    windows = quota_windows(merged, "codex")
    assert windows["5h"]["observed_at"] == current["updated_at"]
    assert windows["weekly"]["observed_at"] == older["updated_at"]


def test_claude_error_is_scoped_to_its_profile(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path)})
    now = datetime.now(timezone.utc)
    for name, seconds in (("first", 20), ("second", 50)):
        service["create_session"](name, "claude")
        service["record_status"](name, {
            "remaining_5h_pct": 60, "remaining_week_pct": 40,
            "source_ref": "api:anthropic-ratelimit-headers",
            "updated_at": (now - timedelta(seconds=seconds)).isoformat(),
        })
    stdout = io.StringIO()
    with mock.patch("src.commands.status._refresh_claude_auth_states", return_value={"errors": []}), \
         mock.patch("src.commands.status._refresh_claude_sessions", return_value={
             "errors": [{"session": "first", "error": "offline", "reason": "quota_read_failed"}],
         }):
        assert main(["status", "--json"], {"service": service, "stdout": stdout, "stderr": io.StringIO()}) == 0
    rows = {row["session_name"]: row for row in json.loads(stdout.getvalue())["rows"]}
    assert rows["first"]["quota_windows"]["5h"]["availability"] == "unavailable"
    assert rows["second"]["quota_windows"]["5h"]["availability"] == "measured"
    assert rows["first"]["quota_windows"]["5h"]["observed_at"] != rows["second"]["quota_windows"]["5h"]["observed_at"]


def test_shared_unattributed_artifact_does_not_date_another_profile(tmp_path):
    service = create_session_service({
        "base_dir": str(tmp_path), "fetchCodexRateLimits": lambda _session: None,
        "env": {"CDX_HOME": str(tmp_path), "CODEX_HOME": str(tmp_path / "shared")},
    })
    service["create_session"]("work", "codex")
    artifact = {"remaining_5h_pct": 80, "updated_at": "2026-11-05T10:00:00+00:00", "structured": True}
    with mock.patch("src.session_service.fetch_codex_rate_limits", return_value=None), \
         mock.patch("src.session_status.find_latest_status_artifact", side_effect=[None, artifact]):
        row = service["get_status_row"]("work", force_refresh=True)
    assert row["quota_windows"]["5h"]["observed_at"] is None


@pytest.mark.parametrize("provider,threshold", [("codex", 300), ("claude", 600)])
def test_freshness_threshold_includes_boundary(provider, threshold):
    now = datetime.now(timezone.utc)
    for seconds, expected in ((threshold - 1, "measured"), (threshold, "stale")):
        status = {"remaining_5h_pct": 0, "updated_at": (now - timedelta(seconds=seconds)).isoformat()}
        assert quota_windows(status, provider, now=now)["5h"]["availability"] == expected
