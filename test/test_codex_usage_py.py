import json
import queue
import unittest

from src.codex_usage import (
    _format_reset_date,
    _get_window,
    _read_response,
    _remaining_from_used_percent,
    codex_auth_lock,
    fetch_codex_rate_limit_diagnostic,
    fetch_codex_rate_limits,
    normalize_codex_rate_limit_snapshot,
)


class FakeStdin:
    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass


class FakePopen:
    """Minimal Popen stand-in: stdout replays pre-seeded JSON-RPC lines."""

    def __init__(self, lines):
        self.stdin = FakeStdin()
        self.stdout = iter(lines)
        self.stderr = iter([])
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


def popen_factory_for(lines):
    return lambda *a, **k: FakePopen(lines)


class CodexUsagePureTests(unittest.TestCase):
    def test_format_reset_date(self):
        self.assertIsNone(_format_reset_date(None))
        self.assertIsNone(_format_reset_date("not-a-number"))
        # 2021-01-01T00:00:00Z; formatted in local tz, so just assert shape.
        out = _format_reset_date(1609459200)
        self.assertRegex(out, r"^[A-Z][a-z]{2} \d{1,2} \d{2}:\d{2}$")

    def test_remaining_from_used_percent_clamps(self):
        self.assertIsNone(_remaining_from_used_percent(None))
        self.assertIsNone(_remaining_from_used_percent("bad"))
        self.assertEqual(_remaining_from_used_percent(0), 100)
        self.assertEqual(_remaining_from_used_percent(100), 0)
        self.assertEqual(_remaining_from_used_percent(150), 0)  # over-used clamps to 0
        self.assertEqual(_remaining_from_used_percent(-20), 100)  # negative clamps to 100
        self.assertEqual(_remaining_from_used_percent(40), 60)

    def test_get_window_matches_either_key_style(self):
        snap = {
            "primary": {"windowDurationMins": 300, "usedPercent": 10},
            "secondary": {"window_minutes": 10080, "used_percent": 20},
        }
        self.assertEqual(_get_window(snap, 300)["usedPercent"], 10)
        self.assertEqual(_get_window(snap, 10080)["used_percent"], 20)
        self.assertEqual(_get_window(snap, 999), {})

    def test_normalize_snapshot_none(self):
        self.assertIsNone(normalize_codex_rate_limit_snapshot(None))

    def test_normalize_snapshot_full(self):
        snap = {
            "primary": {"windowDurationMins": 300, "usedPercent": 40, "resetsAt": 1609459200},
            "secondary": {"windowDurationMins": 10080, "usedPercent": 10, "resetsAt": 1609459200},
            "credits": {"balance": 12, "hasCredits": True},
        }
        out = normalize_codex_rate_limit_snapshot(snap)
        self.assertEqual(out["remaining_5h_pct"], 60)
        self.assertEqual(out["remaining_week_pct"], 90)
        self.assertEqual(out["credits"], 12)
        self.assertEqual(out["source_ref"], "api:codex-app-server-rate-limits")
        self.assertIsNotNone(out["reset_at"])

    def test_normalize_snapshot_zero_credit_balance_is_dropped(self):
        snap = {"credits": {"balance": 0, "hasCredits": False, "unlimited": False}}
        self.assertIsNone(normalize_codex_rate_limit_snapshot(snap)["credits"])

    def test_normalize_snapshot_decimal_zero_credit_balance_is_dropped(self):
        snap = {"credits": {"balance": "0.00", "hasCredits": False, "unlimited": False}}
        self.assertIsNone(normalize_codex_rate_limit_snapshot(snap)["credits"])

    def test_normalize_snapshot_keeps_zero_balance_when_unlimited(self):
        snap = {"credits": {"balance": "0.00", "hasCredits": False, "unlimited": True}}
        self.assertEqual(normalize_codex_rate_limit_snapshot(snap)["credits"], "0.00")

    def test_normalize_snapshot_scalar_credits(self):
        snap = {"credits": 5}
        self.assertEqual(normalize_codex_rate_limit_snapshot(snap)["credits"], 5)


class CodexReadResponseTests(unittest.TestCase):
    def _queue(self, *items):
        q = queue.Queue()
        for it in items:
            q.put(it)
        return q

    def test_returns_matching_id_and_skips_others(self):
        q = self._queue(
            json.dumps({"id": 1, "result": "other"}),
            "not json at all",
            json.dumps({"id": 2, "result": "wanted"}),
        )
        self.assertEqual(_read_response(q, 2, timeout=1)["result"], "wanted")

    def test_none_sentinel_stops(self):
        q = self._queue(json.dumps({"id": 1}), None, json.dumps({"id": 2}))
        self.assertIsNone(_read_response(q, 2, timeout=1))


class CodexProbeTests(unittest.TestCase):
    def setUp(self):
        self.session = {"authHome": "/tmp/does-not-need-to-exist-cdx-test"}

    def _lines(self, ratelimits_result):
        return [
            json.dumps({"id": 1, "result": {}}),
            json.dumps({"id": 2, "result": ratelimits_result}),
        ]

    def test_missing_auth_home(self):
        out = fetch_codex_rate_limit_diagnostic({}, popen_factory=popen_factory_for([]))
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"], "missing_auth_home")

    def test_success(self):
        snap = {"primary": {"windowDurationMins": 300, "usedPercent": 25}}
        lines = self._lines({"rateLimitsByLimitId": {"codex": snap}})
        out = fetch_codex_rate_limit_diagnostic(self.session, popen_factory=popen_factory_for(lines))
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"]["remaining_5h_pct"], 75)

    def test_initialize_failure(self):
        lines = [json.dumps({"id": 1, "error": {"message": "nope"}})]
        out = fetch_codex_rate_limit_diagnostic(self.session, popen_factory=popen_factory_for(lines))
        self.assertEqual(out["reason"], "initialize_failed")

    def test_missing_rate_limits(self):
        lines = self._lines({"rateLimitsByLimitId": {}})  # no codex snapshot
        out = fetch_codex_rate_limit_diagnostic(self.session, popen_factory=popen_factory_for(lines))
        self.assertEqual(out["reason"], "missing_rate_limits")

    def test_codex_cli_not_found(self):
        def boom(*a, **k):
            raise FileNotFoundError("codex")

        out = fetch_codex_rate_limit_diagnostic(self.session, popen_factory=boom)
        self.assertEqual(out["reason"], "codex_cli_not_found")

    def test_fetch_rate_limits_returns_status_or_none(self):
        snap = {"primary": {"windowDurationMins": 300, "usedPercent": 25}}
        lines = self._lines({"rateLimitsByLimitId": {"codex": snap}})
        self.assertIsNotNone(fetch_codex_rate_limits(self.session, popen_factory=popen_factory_for(lines)))
        bad = [json.dumps({"id": 1, "error": {}})]
        self.assertIsNone(fetch_codex_rate_limits(self.session, popen_factory=popen_factory_for(bad)))


class CodexAuthLockTests(unittest.TestCase):
    def test_no_auth_home_is_noop(self):
        with codex_auth_lock(None) as acquired:
            self.assertTrue(acquired)


if __name__ == "__main__":
    unittest.main()
