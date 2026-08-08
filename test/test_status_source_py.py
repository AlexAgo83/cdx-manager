import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from src.errors import CdxError
from src.session_service import _safe_relpath
from src.status_source import (
    _format_local_reset_timestamp,
    extract_named_statuses_from_text,
    find_latest_codex_conversation_id,
    find_latest_status_artifact,
)
from src.status_view import _parse_reset_timestamp


def _write_status_log(path, five_h_left, weekly_left, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"5h limit: [xx] {five_h_left}% left\nWeekly limit: [xx] {weekly_left}% left\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _write_rollout(path, timestamp, primary_used, secondary_used=None, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rate_limits = {
        "primary": {"used_percent": primary_used, "window_minutes": 300, "resets_at": 1783261513},
    }
    if secondary_used is not None:
        rate_limits["secondary"] = {"used_percent": secondary_used, "window_minutes": 10080, "resets_at": 1783413034}
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp": timestamp,
            "payload": {"type": "token_count", "rate_limits": rate_limits},
        }) + "\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class CodexConversationIdTests(unittest.TestCase):
    def _rollout(self, root, name, payload_line, mtime=None):
        path = os.path.join(root, "sessions", "2026", "08", "08", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(payload_line + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def test_reads_the_session_id_from_the_newest_rollout(self):
        root = tempfile.mkdtemp()
        old = "aaaaaaaa-1111-2222-3333-444444444444"
        new = "bbbbbbbb-1111-2222-3333-444444444444"
        self._rollout(root, f"rollout-2026-08-08T07-00-00-{old}.jsonl",
                      json.dumps({"type": "session_meta", "payload": {"session_id": old}}), mtime=1000)
        self._rollout(root, f"rollout-2026-08-08T09-00-00-{new}.jsonl",
                      json.dumps({"type": "session_meta", "payload": {"session_id": new}}), mtime=2000)

        self.assertEqual(find_latest_codex_conversation_id(root), new)

    def test_falls_back_to_the_filename_when_the_first_line_is_unusable(self):
        root = tempfile.mkdtemp()
        identifier = "cccccccc-1111-2222-3333-444444444444"
        self._rollout(root, f"rollout-2026-08-08T09-00-00-{identifier}.jsonl", '{"type": "session_meta"')

        self.assertEqual(find_latest_codex_conversation_id(root), identifier)

    def test_returns_none_rather_than_guessing_when_there_is_no_rollout(self):
        root = tempfile.mkdtemp()
        self.assertIsNone(find_latest_codex_conversation_id(root))
        self.assertIsNone(find_latest_codex_conversation_id(os.path.join(root, "missing")))


class StatusSourcePythonTests(unittest.TestCase):
    def test_extract_named_statuses_from_key_value_text(self):
        text = "\n".join([
            "usage_pct: 12%",
            "remaining_5h_pct=88%",
            "remaining_week_pct: 66%",
            "credits: 1,234 credits",
        ])

        result = extract_named_statuses_from_text(text)

        self.assertEqual(result["usage_pct"], 12)
        self.assertEqual(result["remaining_5h_pct"], 88)
        self.assertEqual(result["remaining_week_pct"], 66)
        self.assertEqual(result["credits"], "1234")

    def test_extract_named_statuses_keeps_decimal_credits_and_drops_zero(self):
        result = extract_named_statuses_from_text("usage_pct: 12%\ncredits: 3.75")
        self.assertEqual(result["credits"], "3.75")

        result = extract_named_statuses_from_text("usage_pct: 12%\ncredits: 0.00")
        self.assertIsNone(result["credits"])

    def test_extract_named_statuses_from_codex_limit_block(self):
        result = extract_named_statuses_from_text("\n".join([
            "│  5h limit:             [████████████░░░░░░░░] 39% left",
            "│                        (resets 02:21 on 16 Apr)            │",
            "│  Weekly limit:         [██████████████░░░░░░] 70% left",
            "│                        (resets 10:10 on 17 Apr)            │",
        ]))

        self.assertEqual(result["usage_pct"], 61)
        self.assertEqual(result["remaining_5h_pct"], 39)
        self.assertEqual(result["remaining_week_pct"], 70)
        self.assertEqual(result["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(result["reset_week_at"], "Apr 17 10:10")

    def test_extract_named_statuses_from_claude_block(self):
        result = extract_named_statuses_from_text("\n".join([
            "Current session",
            "19% used",
            "resets: at 5:00 AM",
            "Current week",
            "25% used",
            "resets: Thursday, April 17 at 5:00 AM",
        ]))

        self.assertEqual(result["usage_pct"], 19)
        self.assertEqual(result["remaining_5h_pct"], 81)
        self.assertEqual(result["remaining_week_pct"], 75)
        self.assertIsNotNone(result["reset_5h_at"])
        self.assertEqual(result["reset_week_at"], "Apr 17 05:00")

    def test_extract_named_statuses_from_claude_no_stats_message(self):
        result = extract_named_statuses_from_text("No stats available yet. Start using Claude Code!")

        self.assertEqual(result["usage_pct"], 0)
        self.assertEqual(result["remaining_5h_pct"], 100)
        self.assertEqual(result["remaining_week_pct"], 100)

    def test_find_latest_status_artifact_selects_most_recent_candidate(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            log_dir = os.path.join(temp_dir, "log")
            old_path = os.path.join(log_dir, "cdx-session-old.log")
            new_path = os.path.join(log_dir, "cdx-session-new.log")
            _write_status_log(old_path, 25, 50, mtime=100)
            _write_status_log(new_path, 80, 90, mtime=200)

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertEqual(result["remaining_5h_pct"], 80)
        self.assertEqual(result["remaining_week_pct"], 90)
        self.assertEqual(result["source_ref"], new_path)

    def test_fresh_structured_rollout_beats_stale_log_status_screen(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            stale_log = os.path.join(temp_dir, "log", "cdx-session-stale.log")
            _write_status_log(stale_log, 44, 59, mtime=100)

            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            _write_rollout(rollout, "2026-07-05T10:37:31.157Z", 93, secondary_used=65, mtime=200)

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertEqual(result["remaining_5h_pct"], 7)
        self.assertEqual(result["remaining_week_pct"], 35)

    def test_structured_rollout_uses_window_duration_when_primary_is_weekly(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            os.makedirs(os.path.dirname(rollout), exist_ok=True)
            with open(rollout, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": "2026-07-05T10:37:31.157Z",
                    "payload": {
                        "type": "token_count",
                        "rate_limits": {
                            "primary": {"used_percent": 20, "window_minutes": 10080, "resets_at": 1783413034},
                            "secondary": {"used_percent": 90, "window_minutes": 300, "resets_at": 1783261513},
                        },
                    },
                }) + "\n")

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertEqual(result["remaining_5h_pct"], 10)
        self.assertEqual(result["remaining_week_pct"], 80)
        self.assertEqual(result["reset_5h_at"], _format_local_reset_timestamp(1783261513))
        self.assertEqual(result["reset_week_at"], _format_local_reset_timestamp(1783413034))

    def test_structured_rollout_does_not_duplicate_weekly_window_as_5h(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            os.makedirs(os.path.dirname(rollout), exist_ok=True)
            with open(rollout, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": "2026-07-05T10:37:31.157Z",
                    "payload": {
                        "type": "token_count",
                        "rate_limits": {
                            "primary": {"used_percent": 20, "window_minutes": 10080, "resets_at": 1783413034},
                            "secondary": None,
                        },
                    },
                }) + "\n")

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertIsNone(result["remaining_5h_pct"])
        self.assertEqual(result["remaining_week_pct"], 80)
        self.assertIsNone(result["reset_5h_at"])
        self.assertEqual(result["reset_week_at"], _format_local_reset_timestamp(1783413034))

    def test_weekly_only_structured_rollout_does_not_backfill_stale_5h(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            stale_log = os.path.join(temp_dir, "log", "cdx-session-stale.log")
            _write_status_log(stale_log, 99, 99, mtime=100)

            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            os.makedirs(os.path.dirname(rollout), exist_ok=True)
            with open(rollout, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": "2026-07-05T10:37:31.157Z",
                    "payload": {
                        "type": "token_count",
                        "rate_limits": {
                            "primary": {"used_percent": 20, "window_minutes": 10080, "resets_at": 1783413034},
                            "secondary": None,
                        },
                    },
                }) + "\n")

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertIsNone(result["remaining_5h_pct"])
        self.assertEqual(result["remaining_week_pct"], 80)
        self.assertIsNone(result["reset_5h_at"])
        self.assertEqual(result["reset_week_at"], _format_local_reset_timestamp(1783413034))

    def test_stale_structured_block_in_hot_rollout_loses_to_fresher_log(self):
        block_time = "2026-07-05T08:00:00Z"
        block_epoch = datetime(2026, 7, 5, 8, 0, 0, tzinfo=timezone.utc).timestamp()

        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            fresh_log = os.path.join(temp_dir, "log", "cdx-session-fresh.log")
            _write_status_log(fresh_log, 44, 59, mtime=block_epoch + 3600)

            # Rollout appended after the log (fresh mtime) but its rate_limits
            # block itself predates the log: the log must win.
            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            _write_rollout(rollout, block_time, 93, secondary_used=65, mtime=block_epoch + 7200)

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertEqual(result["remaining_5h_pct"], 44)
        self.assertEqual(result["remaining_week_pct"], 59)
        self.assertEqual(result["source_ref"], fresh_log)

    def test_partial_structured_winner_keeps_week_value_from_trusted_log(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            stale_log = os.path.join(temp_dir, "log", "cdx-session-stale.log")
            _write_status_log(stale_log, 44, 59, mtime=100)

            # Fresher structured payload carrying only the primary window.
            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            _write_rollout(rollout, "2026-07-05T10:37:31.157Z", 93, mtime=200)

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertEqual(result["remaining_5h_pct"], 7)
        self.assertEqual(result["remaining_week_pct"], 59)
        self.assertIn("rollout.jsonl", result["source_ref"])

    def test_untrusted_root_demotes_unattributed_structured_payloads(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            stale_log = os.path.join(temp_dir, "log", "cdx-session-stale.log")
            _write_status_log(stale_log, 44, 59, mtime=100)

            # Fresher structured payload, but rate_limits JSON carries no
            # account identity: in a shared root it must not outrank the log.
            rollout = os.path.join(temp_dir, "sessions", "2026", "07", "05", "rollout.jsonl")
            _write_rollout(rollout, "2026-07-05T10:37:31.157Z", 93, secondary_used=65, mtime=200)

            result = find_latest_status_artifact(
                temp_dir,
                provider="codex",
                expected_account_email="a@b.com",
                trust_unattributed_structured=False,
            )

        self.assertEqual(result["remaining_5h_pct"], 44)
        self.assertEqual(result["remaining_week_pct"], 59)
        self.assertEqual(result["source_ref"], stale_log)

    def test_safe_relpath_rejects_traversal_and_absolute_paths(self):
        self.assertEqual(_safe_relpath("profile/auth.json"), "profile/auth.json")

        for value in ("", ".", "../evil", "..\\evil", "/tmp/evil", "safe/../../evil"):
            with self.subTest(value=value):
                with self.assertRaises(CdxError):
                    _safe_relpath(value)

    def test_parse_reset_timestamp_accepts_iso_z_and_rejects_invalid(self):
        self.assertIsNotNone(_parse_reset_timestamp("2026-04-17T05:00:00Z"))
        self.assertIsNotNone(_parse_reset_timestamp("2026-04-17T05:00:00+00:00"))
        self.assertIsNone(_parse_reset_timestamp("not a timestamp"))

    def test_parse_reset_timestamp_rolls_year_wraps_to_the_future(self):
        from datetime import datetime, timedelta

        now = datetime.now().astimezone()

        upcoming = (now + timedelta(days=2)).strftime("%b %d %H:%M")
        parsed = _parse_reset_timestamp(upcoming)
        self.assertIsNotNone(parsed)
        self.assertGreater(parsed, now.timestamp())

        # A date ~300 days back can only be last year's rendering of a
        # near-future reset (the "Jan 2 seen on Dec 31" wrap).
        wrapped = (now - timedelta(days=300)).strftime("%b %d %H:%M")
        parsed = _parse_reset_timestamp(wrapped)
        self.assertIsNotNone(parsed)
        self.assertGreater(parsed, now.timestamp())

        # A reset a few days back genuinely passed and must stay in the past.
        passed = (now - timedelta(days=3)).strftime("%b %d %H:%M")
        parsed = _parse_reset_timestamp(passed)
        self.assertIsNotNone(parsed)
        self.assertLess(parsed, now.timestamp())


if __name__ == "__main__":
    unittest.main()
