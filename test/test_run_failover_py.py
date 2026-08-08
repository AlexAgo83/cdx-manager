"""Tests for the rate-limit classification behind `cdx run --failover`.

The asymmetry these tests protect: missing a rate limit costs nothing new,
inventing one migrates a healthy run off a working account. So most of what is
asserted here is what must NOT be classified as exhaustion.
"""

import json
import tempfile
import unittest

from src.run_failover import (
    looks_rate_limited,
    should_fail_over,
    status_confirms_exhaustion,
)


def _stdout(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    return {"returncode": 1, "stdout_path": handle.name}


class LooksRateLimitedTests(unittest.TestCase):
    def test_codex_jsonl_event_carrying_the_marker_is_classified(self):
        run_info = _stdout("\n".join([
            json.dumps({"type": "item.completed", "payload": {"text": "working"}}),
            json.dumps({"type": "error", "payload": {"kind": "rate_limit", "retry_after": 3600}}),
        ]))
        self.assertTrue(looks_rate_limited("codex", run_info))

    def test_claude_result_object_carrying_the_marker_is_classified(self):
        run_info = _stdout(json.dumps({"type": "result", "subtype": "usage limit reached", "is_error": True}))
        self.assertTrue(looks_rate_limited("claude", run_info))

    def test_assistant_prose_about_rate_limits_is_not_classified(self):
        # The model discussing rate limits must never be able to trigger a
        # migration, so the fields holding its own words are not searched.
        run_info = _stdout(json.dumps({
            "type": "result",
            "result": "I added retry handling for when the API returns rate_limit errors.",
        }))
        self.assertFalse(looks_rate_limited("claude", run_info))

    def test_a_plain_failure_is_not_classified(self):
        run_info = _stdout(json.dumps({"type": "result", "subtype": "error_during_execution"}))
        self.assertFalse(looks_rate_limited("claude", run_info))

    def test_a_timeout_is_cdx_own_deadline_not_the_provider_verdict(self):
        run_info = _stdout(json.dumps({"type": "error", "payload": {"kind": "rate_limit"}}))
        run_info["timed_out"] = True
        self.assertFalse(looks_rate_limited("codex", run_info))

    def test_a_successful_run_is_never_classified(self):
        run_info = _stdout(json.dumps({"type": "error", "payload": {"kind": "rate_limit"}}))
        run_info["returncode"] = 0
        self.assertFalse(looks_rate_limited("codex", run_info))

    def test_unparsable_output_is_an_absence_of_signal(self):
        self.assertFalse(looks_rate_limited("codex", _stdout("rate limit reached\ngarbage")))

    def test_missing_output_file_is_not_a_signal(self):
        self.assertFalse(looks_rate_limited("codex", {"returncode": 1, "stdout_path": "/nonexistent"}))
        self.assertFalse(looks_rate_limited("codex", {"returncode": 1}))

    def test_providers_without_a_matcher_are_never_classified(self):
        run_info = _stdout(json.dumps({"type": "error", "payload": {"kind": "rate_limit"}}))
        for provider in ("ollama", "antigravity", None):
            self.assertFalse(looks_rate_limited(provider, run_info))


class StatusCorroborationTests(unittest.TestCase):
    def test_a_spent_window_confirms(self):
        self.assertTrue(status_confirms_exhaustion({"remaining_5h_pct": 0, "remaining_week_pct": 40}))
        self.assertTrue(status_confirms_exhaustion({"remaining_week_pct": 0}))
        self.assertTrue(status_confirms_exhaustion({"blocking": "WEEK"}))

    def test_a_healthy_account_does_not_confirm(self):
        self.assertFalse(status_confirms_exhaustion({"remaining_5h_pct": 50, "remaining_week_pct": 80}))

    def test_an_unreadable_status_does_not_confirm(self):
        # Otherwise every failed probe would read as a rate limit.
        self.assertFalse(status_confirms_exhaustion(None))
        self.assertFalse(status_confirms_exhaustion({}))
        self.assertFalse(status_confirms_exhaustion({"remaining_5h_pct": None}))


class ShouldFailOverTests(unittest.TestCase):
    def test_both_signals_are_required(self):
        limited = _stdout(json.dumps({"type": "error", "payload": {"kind": "rate_limit"}}))
        healthy = _stdout(json.dumps({"type": "result", "subtype": "error_during_execution"}))
        spent = {"remaining_week_pct": 0}
        fine = {"remaining_5h_pct": 90, "remaining_week_pct": 90}

        self.assertTrue(should_fail_over("codex", limited, spent))
        self.assertFalse(should_fail_over("codex", limited, fine))
        self.assertFalse(should_fail_over("codex", healthy, spent))
        self.assertFalse(should_fail_over("codex", healthy, fine))
