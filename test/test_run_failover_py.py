"""Tests for the rate-limit classification behind `cdx run --failover`.

The asymmetry these tests protect: missing a rate limit costs nothing new,
inventing one migrates a healthy run off a working account. So most of what is
asserted here is what must NOT be classified as exhaustion.
"""

import json
import tempfile
import unittest

from src.run_failover import (
    failover_reason,
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
    def test_the_real_codex_exhaustion_output_is_classified(self):
        """Captured verbatim from codex-cli 0.147.0 on an exhausted account.

        The first version of the matcher missed this on both counts: it had no
        marker for "out of credits", and it excluded the `message` key that
        codex actually puts the text in.
        """
        run_info = _stdout("\n".join([
            json.dumps({"type": "thread.started", "thread_id": "019fe305-b9dd-7c42-b688-e37bdaae5626"}),
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "error", "message": "Your workspace is out of credits. Add credits to continue."}),
            json.dumps({"type": "turn.failed", "error": {"message": "Your workspace is out of credits. Add credits to continue."}}),
        ]))
        self.assertTrue(looks_rate_limited("codex", run_info))

    def test_codex_rate_limit_wording_is_classified(self):
        run_info = _stdout(json.dumps({"type": "error", "message": "Rate limit reached. Try again later."}))
        self.assertTrue(looks_rate_limited("codex", run_info))

    def test_claude_error_result_carrying_the_marker_is_classified(self):
        run_info = _stdout(json.dumps({
            "type": "result", "is_error": True, "result": "Usage limit reached for this account.",
        }))
        self.assertTrue(looks_rate_limited("claude", run_info))

    def test_assistant_prose_about_rate_limits_is_not_classified(self):
        # The model discussing rate limits must never be able to trigger a
        # migration, so the fields holding its own words are not searched.
        run_info = _stdout(json.dumps({
            "type": "result", "is_error": False,
            "result": "I added retry handling for when the workspace is out of credits.",
        }))
        self.assertFalse(looks_rate_limited("claude", run_info))

    def test_a_plain_failure_is_not_classified(self):
        run_info = _stdout(json.dumps({"type": "result", "is_error": True, "result": "Tool call failed."}))
        self.assertFalse(looks_rate_limited("claude", run_info))
        self.assertFalse(looks_rate_limited("codex", _stdout(json.dumps(
            {"type": "error", "message": "Not inside a trusted directory."}
        ))))

    def test_a_timeout_is_cdx_own_deadline_not_the_provider_verdict(self):
        run_info = _stdout(json.dumps({"type": "error", "message": "Your workspace is out of credits."}))
        run_info["timed_out"] = True
        self.assertFalse(looks_rate_limited("codex", run_info))

    def test_a_successful_run_is_never_classified(self):
        run_info = _stdout(json.dumps({"type": "error", "message": "Your workspace is out of credits."}))
        run_info["returncode"] = 0
        self.assertFalse(looks_rate_limited("codex", run_info))

    def test_unparsable_output_is_an_absence_of_signal(self):
        self.assertFalse(looks_rate_limited("codex", _stdout("rate limit reached\ngarbage")))

    def test_missing_output_file_is_not_a_signal(self):
        self.assertFalse(looks_rate_limited("codex", {"returncode": 1, "stdout_path": "/nonexistent"}))
        self.assertFalse(looks_rate_limited("codex", {"returncode": 1}))

    def test_providers_without_a_matcher_are_never_classified(self):
        run_info = _stdout(json.dumps({"type": "error", "message": "Your workspace is out of credits."}))
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


class UnknownWordingTests(unittest.TestCase):
    """The wording is not one thing, so it cannot be the only gate.

    Only the enterprise "out of credits" sentence has ever been observed. A
    personal plan hitting its 5-hour window, and Claude's own phrasing, are
    different sentences nobody has captured - and a matcher that needs the right
    phrase would silently never fire for them.
    """

    def test_an_unrecognised_failure_still_migrates_when_the_account_is_spent(self):
        unknown = _stdout(json.dumps({
            "type": "error",
            "message": "You have hit your 5-hour usage window for this plan; it resets at 18:00.",
        }))

        self.assertEqual(
            failover_reason("codex", unknown, {"remaining_5h_pct": 0}),
            "account_status_exhausted",
        )

    def test_claude_wording_nobody_has_captured_still_migrates(self):
        unknown = _stdout(json.dumps({
            "type": "result", "is_error": True, "result": "Some phrasing cdx has never seen.",
        }))

        self.assertEqual(
            failover_reason("claude", unknown, {"blocking": "WEEK"}),
            "account_status_exhausted",
        )

    def test_recognised_wording_is_still_reported_as_the_precise_route(self):
        known = _stdout(json.dumps({
            "type": "error", "message": "Your workspace is out of credits.",
        }))

        self.assertEqual(
            failover_reason("codex", known, {"remaining_week_pct": 0}),
            "provider_reported_exhaustion",
        )

    def test_a_healthy_account_is_never_abandoned_whatever_the_run_said(self):
        for payload in (
            {"type": "error", "message": "Your workspace is out of credits."},
            {"type": "error", "message": "Some unrecognised failure."},
        ):
            self.assertIsNone(failover_reason(
                "codex", _stdout(json.dumps(payload)), {"remaining_5h_pct": 90, "remaining_week_pct": 90},
            ))

    def test_a_successful_run_on_a_spent_account_does_not_migrate(self):
        run_info = _stdout(json.dumps({"type": "error", "message": "Your workspace is out of credits."}))
        run_info["returncode"] = 0
        self.assertIsNone(failover_reason("codex", run_info, {"remaining_week_pct": 0}))


class ShouldFailOverTests(unittest.TestCase):
    def test_both_signals_are_required(self):
        limited = _stdout(json.dumps({"type": "error", "message": "Your workspace is out of credits."}))
        healthy = _stdout(json.dumps({"type": "error", "message": "Not inside a trusted directory."}))
        spent = {"remaining_week_pct": 0}
        fine = {"remaining_5h_pct": 90, "remaining_week_pct": 90}

        self.assertTrue(should_fail_over("codex", limited, spent))
        self.assertFalse(should_fail_over("codex", limited, fine))
        # `healthy` is a provider error on a spent account, which the status
        # route now migrates on: the account cannot serve the task regardless of
        # what the message said.
        self.assertTrue(should_fail_over("codex", healthy, spent))
        self.assertFalse(should_fail_over("codex", healthy, fine))
