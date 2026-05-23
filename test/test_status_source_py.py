import os
import tempfile
import unittest

from src.errors import CdxError
from src.session_service import _safe_relpath
from src.status_source import extract_named_statuses_from_text, find_latest_status_artifact
from src.status_view import _parse_reset_timestamp


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
        self.assertEqual(result["credits"], 1234)

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

    def test_find_latest_status_artifact_selects_most_recent_candidate(self):
        with tempfile.TemporaryDirectory(prefix="cdx-status-source-") as temp_dir:
            log_dir = os.path.join(temp_dir, "log")
            os.makedirs(log_dir, exist_ok=True)
            old_path = os.path.join(log_dir, "cdx-session-old.log")
            new_path = os.path.join(log_dir, "cdx-session-new.log")
            with open(old_path, "w", encoding="utf-8") as handle:
                handle.write("5h limit: [xx] 25% left\nWeekly limit: [xx] 50% left\n")
            with open(new_path, "w", encoding="utf-8") as handle:
                handle.write("5h limit: [xx] 80% left\nWeekly limit: [xx] 90% left\n")
            os.utime(old_path, (100, 100))
            os.utime(new_path, (200, 200))

            result = find_latest_status_artifact(temp_dir, provider="codex")

        self.assertEqual(result["remaining_5h_pct"], 80)
        self.assertEqual(result["remaining_week_pct"], 90)
        self.assertEqual(result["source_ref"], new_path)

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


if __name__ == "__main__":
    unittest.main()
