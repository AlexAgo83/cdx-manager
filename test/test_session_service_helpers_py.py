import os
import unittest

from src.errors import CdxError
from src.session_service import (
    _compute_available_pct,
    _is_low_confidence_status_source,
    _is_status_newer,
    _merge_status_payload,
    _normalize_pct_value,
    _normalize_status_payload,
    _parse_status_timeout_seconds,
    _parse_status_timestamp,
    _process_is_running,
    _safe_relpath,
    _status_has_more_detail,
    _to_local_iso,
)


class ProcessRunningTests(unittest.TestCase):
    def test_bad_or_nonpositive_pid(self):
        self.assertFalse(_process_is_running(None))
        self.assertFalse(_process_is_running("nope"))
        self.assertFalse(_process_is_running(0))
        self.assertFalse(_process_is_running(-1))

    def test_current_process_is_running(self):
        self.assertTrue(_process_is_running(os.getpid()))


class SafeRelpathTests(unittest.TestCase):
    def test_safe_relative_path(self):
        self.assertEqual(_safe_relpath("sub/dir/file.txt"), "sub/dir/file.txt")

    def test_rejects_unsafe_paths(self):
        for bad in ("", "/etc/passwd", "..", "../escape", "C:/win"):
            with self.subTest(bad=bad), self.assertRaises(CdxError):
                _safe_relpath(bad)


class ToLocalIsoTests(unittest.TestCase):
    def test_empty_passthrough(self):
        self.assertEqual(_to_local_iso(""), "")
        self.assertIsNone(_to_local_iso(None))

    def test_bad_value_passthrough(self):
        self.assertEqual(_to_local_iso("not-a-date"), "not-a-date")

    def test_z_suffix_parsed_to_local(self):
        out = _to_local_iso("2021-01-01T00:00:00Z")
        # round-trips to an offset-aware local ISO string (no trailing Z)
        self.assertNotIn("Z", out)
        self.assertTrue(out.startswith("20"))


class PctTests(unittest.TestCase):
    def test_normalize_pct_value(self):
        self.assertIsNone(_normalize_pct_value(None))
        self.assertIsNone(_normalize_pct_value("bad"))
        self.assertEqual(_normalize_pct_value(-5), 0)
        self.assertEqual(_normalize_pct_value(150), 100)
        self.assertEqual(_normalize_pct_value(42.6), 43)

    def test_compute_available_pct_is_min(self):
        self.assertIsNone(_compute_available_pct(None))
        self.assertIsNone(_compute_available_pct({}))
        self.assertEqual(
            _compute_available_pct({"remaining_5h_pct": 80, "remaining_week_pct": 30}),
            30,
        )
        self.assertEqual(_compute_available_pct({"remaining_5h_pct": 55}), 55)


class NormalizeStatusPayloadTests(unittest.TestCase):
    def test_defaults_for_empty(self):
        out = _normalize_status_payload(None)
        self.assertIsNone(out["usage_pct"])
        self.assertIsNotNone(out["updated_at"])  # filled with now

    def test_reset_at_fallback_chain(self):
        out = _normalize_status_payload({"reset_5h_at": "5h", "reset_week_at": "wk"})
        self.assertEqual(out["reset_at"], "wk")  # week preferred over 5h
        out2 = _normalize_status_payload({"reset_5h_at": "5h"})
        self.assertEqual(out2["reset_at"], "5h")


class StatusTimeTests(unittest.TestCase):
    def test_parse_status_timestamp(self):
        self.assertIsNone(_parse_status_timestamp(None))
        self.assertIsNone(_parse_status_timestamp("bad"))
        self.assertIsNotNone(_parse_status_timestamp("2021-01-01T00:00:00Z"))

    def test_parse_status_timeout_seconds(self):
        self.assertIsNone(_parse_status_timeout_seconds(None))
        self.assertIsNone(_parse_status_timeout_seconds(""))
        self.assertIsNone(_parse_status_timeout_seconds("bad"))
        self.assertIsNone(_parse_status_timeout_seconds(0))
        self.assertIsNone(_parse_status_timeout_seconds(-3))
        self.assertEqual(_parse_status_timeout_seconds("2.5"), 2.5)


class StatusMergeTests(unittest.TestCase):
    def test_is_status_newer(self):
        old = {"updated_at": "2021-01-01T00:00:00Z"}
        new = {"updated_at": "2022-01-01T00:00:00Z"}
        self.assertFalse(_is_status_newer(None, old))
        self.assertTrue(_is_status_newer(new, None))
        self.assertTrue(_is_status_newer(new, old))
        self.assertFalse(_is_status_newer(old, new))

    def test_has_more_detail(self):
        self.assertFalse(_status_has_more_detail(None, {}))
        self.assertTrue(_status_has_more_detail({"credits": 5}, None))
        self.assertTrue(_status_has_more_detail({"credits": 5}, {"credits": None}))
        self.assertFalse(_status_has_more_detail({"credits": 5}, {"credits": 1}))

    def test_merge_fills_only_missing_fields(self):
        current = {"usage_pct": 10, "credits": None, "updated_at": "2022-01-01T00:00:00Z"}
        candidate = {"usage_pct": 99, "credits": 7, "updated_at": "2021-01-01T00:00:00Z"}
        merged = _merge_status_payload(current, candidate)
        self.assertEqual(merged["usage_pct"], 10)  # current kept
        self.assertEqual(merged["credits"], 7)  # missing filled from candidate
        self.assertEqual(merged["updated_at"], "2022-01-01T00:00:00Z")  # the later stamp wins

    def test_merge_handles_empty_sides(self):
        self.assertEqual(_merge_status_payload(None, {"a": 1}), {"a": 1})
        self.assertEqual(_merge_status_payload({"a": 1}, None), {"a": 1})


class LowConfidenceSourceTests(unittest.TestCase):
    def test_rollout_session_source_is_low_confidence(self):
        self.assertFalse(_is_low_confidence_status_source(None))
        self.assertFalse(_is_low_confidence_status_source({"source_ref": "api:codex"}))
        self.assertTrue(
            _is_low_confidence_status_source({"source_ref": "/home/u/sessions/x/rollout-1.jsonl"})
        )


if __name__ == "__main__":
    unittest.main()
