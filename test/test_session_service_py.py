import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from src.errors import CdxError
from src.session_service import create_session_service
from src.session_store import create_session_store


class SessionServicePythonTests(unittest.TestCase):
    def make_temp_dir(self):
        return tempfile.mkdtemp(prefix="cdx-service-py-")

    def test_create_list_and_remove_sessions(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        service["create_session"]("work1", "claude")

        rows = service["format_list_rows"]()
        self.assertEqual([row["name"] for row in rows], ["main", "work1"])

        service["remove_session"]("main")
        self.assertEqual([s["name"] for s in service["list_sessions"]()], ["work1"])

    def test_create_session_uses_private_directory_permissions_on_unix(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        if os.name == "nt":
            self.skipTest("permission bits are not portable on Windows")

        session_root = service["get_session_root"]("main")
        auth_home = service["get_session"]("main")["authHome"]
        self.assertEqual(oct(os.stat(session_root).st_mode & 0o777), "0o700")
        self.assertEqual(oct(os.stat(auth_home).st_mode & 0o777), "0o700")

    def test_status_rows_do_not_expose_auth_home(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        rows = service["get_status_rows"]()
        self.assertNotIn("auth_home", rows[0])

    def test_remove_session_surfaces_profile_delete_failure(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        profile_root = service["get_session_root"]("main")
        self.assertTrue(os.path.exists(profile_root))

        with mock.patch("src.session_service.shutil.rmtree", side_effect=OSError("locked")):
            with self.assertRaisesRegex(CdxError, "failed to delete archived profile"):
                service["remove_session"]("main")

        self.assertIsNone(service["get_session"]("main"))
        quarantined = [
            name for name in os.listdir(os.path.dirname(profile_root))
            if name.startswith(".main.remove.")
        ]
        self.assertEqual(len(quarantined), 1)

    def test_launch_rehydrates_state_and_missing_state_fails(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        launched = service["launch_session"]("main")
        self.assertEqual(launched["name"], "main")
        self.assertEqual(launched["lastLaunchedAt"], launched["updatedAt"])

        service["create_session"]("work1")
        os.remove(os.path.join(temp_dir, "state", "work1.json"))
        with self.assertRaises(CdxError):
            service["launch_session"]("work1")

    def test_rejects_duplicates_and_unknown_providers(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        with self.assertRaises(CdxError):
            service["create_session"]("main")
        with self.assertRaises(CdxError):
            service["create_session"]("other", "invalid")

    def test_rejects_reserved_session_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        with self.assertRaisesRegex(CdxError, "Session name is reserved: add"):
            service["create_session"]("add")

    def test_rejects_invalid_session_name_shapes(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        with self.assertRaisesRegex(CdxError, "control characters"):
            service["create_session"]("bad\nname")
        with self.assertRaisesRegex(CdxError, "start or end with whitespace"):
            service["create_session"](" bad")
        with self.assertRaisesRegex(CdxError, "too long"):
            service["create_session"]("a" * 65)

    def test_status_rows_are_sorted_by_recency(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        service["create_session"]("work1", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 39,
            "remaining_week_pct": 70,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 16 10:10",
            "updated_at": "2026-04-15T09:00:00+00:00",
        })
        service["record_status"]("work1", {
            "remaining_5h_pct": 56,
            "remaining_week_pct": 81,
            "reset_5h_at": "Apr 17 05:00",
            "reset_week_at": "Apr 17 22:00",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[1]["session_name"], "main")

    def test_status_rows_can_be_derived_from_codex_artifact(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████░░░░░░░░] 39% left",
                "│                        (resets 02:21 on 16 Apr)            │",
                "│  Weekly limit:         [██████████████░░░░░░] 70% left",
                "│                        (resets 10:10 on 17 Apr)            │",
                "│  Credits:              453 credits",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "main")
        self.assertEqual(rows[0]["available_pct"], 39)
        self.assertEqual(rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(rows[0]["remaining_week_pct"], 70)
        self.assertEqual(rows[0]["credits"], 453)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(rows[0]["reset_at"], "Apr 17 10:10")

    def test_derived_codex_status_is_persisted_after_log_disappears(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████░░░░░░░░] 39% left",
                "│                        (resets 02:21 on 16 Apr)            │",
                "│  Weekly limit:         [██████████████░░░░░░] 70% left",
                "│                        (resets 10:10 on 17 Apr)            │",
            ]))

        first_rows = service["get_status_rows"]()
        self.assertEqual(first_rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(first_rows[0]["remaining_week_pct"], 70)

        os.remove(session_log)
        reloaded = create_session_service({"base_dir": temp_dir})
        second_rows = reloaded["get_status_rows"]()
        self.assertEqual(second_rows[0]["available_pct"], 39)
        self.assertEqual(second_rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(second_rows[0]["remaining_week_pct"], 70)
        self.assertEqual(second_rows[0]["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(second_rows[0]["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(second_rows[0]["reset_at"], "Apr 17 10:10")

    def test_incomplete_cached_status_is_enriched_from_same_timestamp_artifact(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1")

        session_log = os.path.join(temp_dir, "profiles", "work1", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████████████] 100% left",
                "│                        (resets 04:03 on 16 Apr)",
                "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
                "│                        (resets 00:08 on 18 Apr)",
            ]))

        status_updated_at = "2026-04-15T21:03:59.270502+00:00"
        service["record_status"]("work1", {
            "usage_pct": 0,
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_at": "Apr 18 00:08",
            "updated_at": status_updated_at,
            "raw_status_text": "cached-but-incomplete",
        })
        os.utime(session_log, (
            datetime.fromisoformat(status_updated_at).timestamp(),
            datetime.fromisoformat(status_updated_at).timestamp(),
        ))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 04:03")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 18 00:08")

        reloaded = create_session_service({"base_dir": temp_dir})
        persisted = reloaded["get_session"]("work1")["lastStatus"]
        self.assertEqual(persisted["reset_5h_at"], "Apr 16 04:03")
        self.assertEqual(persisted["reset_week_at"], "Apr 18 00:08")

    def test_status_rows_can_be_derived_from_claude_artifact(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1", "claude")

        session_log = os.path.join(temp_dir, "profiles", "work1", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "Current session",
                "0% used",
                "Current week",
                "14% used",
                "Resets Thursday, April 17",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[0]["provider"], "claude")
        self.assertEqual(rows[0]["available_pct"], 86)
        self.assertEqual(rows[0]["remaining_5h_pct"], 100)
        self.assertEqual(rows[0]["remaining_week_pct"], 86)
        self.assertIsNone(rows[0]["reset_5h_at"])
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17")
        self.assertEqual(rows[0]["reset_at"], "Apr 17")

    def test_jsonl_payload_with_multiple_embedded_status_blocks_uses_latest_block(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work2")

        history_path = os.path.join(temp_dir, "profiles", "work2", "history.jsonl")
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        payload = "\n".join([
            "Some user text before",
            "│  5h limit:             [████████████████████] 100% left",
            "│                        (resets 04:03 on 16 Apr)",
            "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
            "│                        (resets 00:08 on 18 Apr)",
            "To continue this session, run codex resume older-session",
            "More unrelated text between blocks",
            "│  5h limit:             [████████████████░░░░] 81% left",
            "│                        (resets 03:48 on 16 Apr)",
            "│  Weekly limit:         [████████████████░░░░] 82% left",
            "│                        (resets 16:51 on 22 Apr)",
            "To continue this session, run codex resume newer-session",
        ])
        with open(history_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-15T21:05:09.350492Z",
                "payload": {"text": payload},
            }))
            handle.write("\n")

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work2")
        self.assertEqual(rows[0]["available_pct"], 81)
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")
        self.assertEqual(rows[0]["reset_at"], "Apr 22 16:51")

    def test_log_artifact_wins_over_newer_conversational_jsonl_noise(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work2")

        session_root = os.path.join(temp_dir, "profiles", "work2")
        session_log = os.path.join(session_root, "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
                "To continue this session, run codex resume newer-session",
            ]))

        rollout_path = os.path.join(session_root, "sessions", "2026", "04", "15", "rollout.jsonl")
        os.makedirs(os.path.dirname(rollout_path), exist_ok=True)
        noisy_payload = "\n".join([
            "assistant recap",
            "│  5h limit:             [████████████████████] 100% left",
            "│                        (resets 04:03 on 16 Apr)",
            "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
            "│                        (resets 00:08 on 18 Apr)",
            "To continue this session, run codex resume older-session",
        ])
        with open(rollout_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-15T21:07:17.358831Z",
                "payload": {"text": noisy_payload},
            }))
            handle.write("\n")

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["available_pct"], 81)
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")
        self.assertEqual(rows[0]["reset_at"], "Apr 22 16:51")

    def test_latest_block_in_same_log_wins(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████░░░░░░░░] 60% left",
                "│                        (resets 01:00 on 16 Apr)",
                "│  Weekly limit:         [████████████░░░░░░░░] 60% left",
                "│                        (resets 09:00 on 18 Apr)",
                "To continue this session, run codex resume older-session",
                "noise",
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
                "To continue this session, run codex resume newer-session",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["available_pct"], 81)
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")
        self.assertEqual(rows[0]["reset_at"], "Apr 22 16:51")

    def test_noisy_ansi_transcript_still_parses(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        noisy = (
            "\x1b[31mgarbage before\x1b[0m\n"
            "│  5h limit:             [████████████████░░░░] 81% left\r\n"
            "│                        (resets 03:48 on 16 Apr)\r\n"
            "\x1b]0;title\x07"
            "│  Weekly limit:         [████████████████░░░░] 82% left\r\n"
            "│                        (resets 16:51 on 22 Apr)\r\n"
            "To continue this session, run codex resume noisy-session\r\n"
            "garbage after 123%\n"
        )
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write(noisy)

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)

    def test_narrow_codex_status_transcript_still_parses_resets(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1")

        session_log = os.path.join(temp_dir, "profiles", "work1", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        narrow = (
            "\x1b[39;49m\x1b[K/status\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│  5h limit:             \x1b[22m[████████████████████] 100\x1b[2m │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│                        (resets 04:38 on 16 Apr)   │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│  Weekly limit:         \x1b[22m[█░░░░░░░░░░░░░░░░░░░] 6% \x1b[2m │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│                        (resets 00:08 on 18 Apr)   │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m╰───────────────────────────────────────────────────╯\x1b[39m\x1b[49m\x1b[0m\n"
            "To continue this session, run codex resume 019d9315-0549-7ab0-95fd-b36d812836db\n"
        )
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write(narrow)

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[0]["remaining_5h_pct"], 100)
        self.assertEqual(rows[0]["remaining_week_pct"], 6)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 04:38")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 18 00:08")

    def test_large_status_log_is_tailed(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("old noise\n" * 70000)
            handle.write("\n".join([
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)

    def test_direct_status_log_is_used_even_with_many_newer_history_files(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_root = os.path.join(temp_dir, "profiles", "main")
        session_log = os.path.join(session_root, "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
            ]))

        history_dir = os.path.join(session_root, "sessions", "2026", "04", "16")
        os.makedirs(history_dir, exist_ok=True)
        for index in range(80):
            path = os.path.join(history_dir, f"noise-{index}.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": f"2026-04-16T10:{index % 60:02d}:00.000Z",
                    "payload": {"text": "conversation without status"},
                }))
                handle.write("\n")

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)

    def test_copy_session_overwrites_and_keeps_isolation(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["create_session"]("dest")

        source_log = os.path.join(temp_dir, "profiles", "source", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "Current session",
                "10% used",
                "Current week",
                "20% used",
                "Resets Thursday, April 17",
            ]))

        result = service["copy_session"]("source", "dest")
        self.assertTrue(result["overwritten"])
        copied = service["get_session"]("dest")
        self.assertEqual(copied["provider"], "claude")
        self.assertTrue(copied["authHome"].endswith(os.path.join("dest", "claude-home")))
        self.assertTrue(os.path.exists(os.path.join(temp_dir, "profiles", "dest", "claude-home", "log", "cdx-session.log")))

    def test_copy_session_preserves_destination_when_copy_fails(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["create_session"]("dest")

        dest_marker = os.path.join(temp_dir, "profiles", "dest", "marker.txt")
        with open(dest_marker, "w", encoding="utf-8") as handle:
            handle.write("keep")

        with mock.patch("src.session_service.shutil.copytree", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                service["copy_session"]("source", "dest")

        dest = service["get_session"]("dest")
        self.assertEqual(dest["provider"], "codex")
        self.assertTrue(os.path.exists(dest_marker))

    def test_copy_session_preserves_destination_when_store_replace_fails(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["create_session"]("dest")

        source_log = os.path.join(temp_dir, "profiles", "source", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("source")
        dest_marker = os.path.join(temp_dir, "profiles", "dest", "marker.txt")
        with open(dest_marker, "w", encoding="utf-8") as handle:
            handle.write("keep")

        def write_json(file_path, value):
            if file_path.endswith(os.path.join("state", "dest.json")):
                raise OSError("state write failed")
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")

        with mock.patch("src.session_store._write_json", side_effect=write_json):
            with self.assertRaises(OSError):
                service["copy_session"]("source", "dest")

        dest = service["get_session"]("dest")
        self.assertEqual(dest["provider"], "codex")
        self.assertTrue(os.path.exists(dest_marker))
        self.assertFalse(os.path.exists(os.path.join(temp_dir, "profiles", "dest", "claude-home", "log", "cdx-session.log")))

    def test_copy_session_rejects_reserved_destination_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source")

        with self.assertRaisesRegex(CdxError, "Session name is reserved: add"):
            service["copy_session"]("source", "add")

    def test_rename_session_moves_profile_and_state(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["record_status"]("source", {
            "remaining_5h_pct": 90,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        source_log = os.path.join(temp_dir, "profiles", "source", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Current session\n10% used\nCurrent week\n20% used\n")

        renamed = service["rename_session"]("source", "dest")
        self.assertEqual(renamed["name"], "dest")
        self.assertEqual(renamed["provider"], "claude")
        self.assertIsNone(service["get_session"]("source"))
        self.assertEqual(service["get_session"]("dest")["lastStatus"]["remaining_5h_pct"], 90)
        self.assertFalse(os.path.exists(os.path.join(temp_dir, "profiles", "source")))
        self.assertTrue(os.path.exists(os.path.join(temp_dir, "profiles", "dest", "claude-home", "log", "cdx-session.log")))
        self.assertFalse(os.path.exists(os.path.join(temp_dir, "state", "source.json")))
        self.assertTrue(os.path.exists(os.path.join(temp_dir, "state", "dest.json")))
        self.assertEqual(service["launch_session"]("dest")["name"], "dest")

    def test_rename_session_rejects_existing_and_reserved_destination_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source")
        service["create_session"]("dest")

        with self.assertRaisesRegex(CdxError, "Session already exists: dest"):
            service["rename_session"]("source", "dest")
        with self.assertRaisesRegex(CdxError, "Session name is reserved: add"):
            service["rename_session"]("source", "add")

    def test_reset_date_formats_are_supported(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        from datetime import timedelta

        fixtures = [
            ("main1", [
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 21:51)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
            ], "time-only", "Apr 22 16:51"),
            ("main2", [
                "Current session",
                "12% used",
                "Current week",
                "34% used",
                "Resets Thursday, April 17",
            ], None, "Apr 17"),
            ("main3", [
                "Current session",
                "12% used",
                "Current week",
                "34% used",
                "Resets April 17, 2026",
            ], None, "Apr 17"),
            ("main4", [
                "Current session",
                "12% used",
                "Resets at 5:00 AM",
                "Current week",
                "34% used",
                "Resets Thursday, April 17",
            ], "ampm-time-only", "Apr 17"),
            ("main5", [
                "Current session",
                "12% used",
                "Resets Thursday, April 17 at 5:00 AM",
                "Current week",
                "34% used",
                "Resets Thursday, April 24",
            ], "Apr 17 05:00", "Apr 24"),
        ]

        for name, lines, expected_5h, expected_week in fixtures:
            provider = "claude" if lines[0].startswith("Current session") else "codex"
            service["create_session"](name, provider if provider == "claude" else "codex")
            root = os.path.join(temp_dir, "profiles", name, "claude-home" if provider == "claude" else "")
            session_log = os.path.join(root, "log", "cdx-session.log")
            os.makedirs(os.path.dirname(session_log), exist_ok=True)
            with open(session_log, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            rows = [row for row in service["get_status_rows"]() if row["session_name"] == name]
            if expected_5h == "time-only":
                now = datetime.now().astimezone()
                candidate = datetime(now.year, now.month, now.day, 21, 51, tzinfo=now.tzinfo)
                if candidate <= now:
                    candidate = candidate + timedelta(days=1)
                expected_5h = f"{candidate.strftime('%b')} {candidate.day} 21:51"
            if expected_5h == "ampm-time-only":
                now = datetime.now().astimezone()
                candidate = datetime(now.year, now.month, now.day, 5, 0, tzinfo=now.tzinfo)
                if candidate <= now:
                    candidate = candidate + timedelta(days=1)
                expected_5h = f"{candidate.strftime('%b')} {candidate.day} 05:00"
            self.assertEqual(rows[0]["reset_5h_at"], expected_5h)
            self.assertEqual(rows[0]["reset_week_at"], expected_week)

    def test_claude_log_wins_over_newer_jsonl_noise(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude1", "claude")

        session_root = os.path.join(temp_dir, "profiles", "claude1", "claude-home")
        session_log = os.path.join(session_root, "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "Current session",
                "10% used",
                "Current week",
                "20% used",
                "Resets Thursday, April 17",
                "Extra usage",
            ]))

        rollout_path = os.path.join(session_root, "sessions", "2026", "04", "15", "rollout.jsonl")
        os.makedirs(os.path.dirname(rollout_path), exist_ok=True)
        with open(rollout_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-15T21:07:17.358831Z",
                "payload": {
                    "text": "\n".join([
                        "chat transcript",
                        "Current session",
                        "90% used",
                        "Current week",
                        "95% used",
                        "Resets Thursday, April 24",
                        "Extra usage",
                    ]),
                },
            }))
            handle.write("\n")

        rows = [row for row in service["get_status_rows"]() if row["session_name"] == "claude1"]
        self.assertEqual(rows[0]["remaining_5h_pct"], 90)
        self.assertEqual(rows[0]["remaining_week_pct"], 80)
        self.assertIsNone(rows[0]["reset_5h_at"])
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17")
        self.assertEqual(rows[0]["reset_at"], "Apr 17")

    def test_codex_status_ignores_pasted_other_account_block(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work2")

        auth_path = os.path.join(temp_dir, "profiles", "work2", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "tokens": {
                    "id_token": "." + "eyJlbWFpbCI6ICJ0b21AZXhhbXBsZS5jb20ifQ" + ".",
                },
            }))

        session_log = os.path.join(temp_dir, "profiles", "work2", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  Account:              tom@example.com (Team)",
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
                "To continue this session, run codex resume work2-session",
                "",
                "pasted from another account:",
                "│  Account:              alex@example.com (Business)",
                "│  5h limit:             [████████████████████] 100% left",
                "│                        (resets 04:38 on 16 Apr)",
                "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
                "│                        (resets 00:08 on 18 Apr)",
                "To continue this session, run codex resume other-session",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work2")
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")

    def test_corrupted_sessions_json_raises(self):
        temp_dir = self.make_temp_dir()
        store_file = os.path.join(temp_dir, "sessions.json")
        os.makedirs(temp_dir, exist_ok=True)
        with open(store_file, "w", encoding="utf-8") as handle:
            handle.write("{bad json")
        store = create_session_store(temp_dir)
        with self.assertRaisesRegex(CdxError, "Corrupt JSON file"):
            store["list_sessions"]()

    def test_corrupted_state_file_fails_launch(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        state_path = os.path.join(temp_dir, "state", "main.json")
        with open(state_path, "w", encoding="utf-8") as handle:
            handle.write("{bad json")
        with self.assertRaisesRegex(CdxError, "Corrupt JSON file"):
            service["launch_session"]("main")

    def test_session_store_uses_windows_file_locking_when_requested(self):
        temp_dir = self.make_temp_dir()
        calls = []
        fake_msvcrt = SimpleNamespace(
            LK_LOCK=1,
            LK_UNLCK=2,
            locking=lambda fd, mode, length: calls.append((fd, mode, length)),
        )

        with mock.patch("sys.platform", "win32"):
            with mock.patch.dict(sys.modules, {"msvcrt": fake_msvcrt}):
                store = create_session_store(temp_dir)
                store["list_sessions"]()

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1:], (1, 1))
        self.assertEqual(calls[1][1:], (2, 1))


if __name__ == "__main__":
    unittest.main()
