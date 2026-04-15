import json
import os
import tempfile
import unittest

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

    def test_status_rows_are_sorted_by_recency(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        service["create_session"]("work1", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 39,
            "remaining_week_pct": 70,
            "reset_at": "Apr 16",
            "updated_at": "2026-04-15T09:00:00+00:00",
        })
        service["record_status"]("work1", {
            "remaining_5h_pct": 56,
            "remaining_week_pct": 81,
            "reset_at": "Apr 17",
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
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "main")
        self.assertEqual(rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(rows[0]["remaining_week_pct"], 70)
        self.assertEqual(rows[0]["reset_at"], "Apr 17 10:10")

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
        self.assertEqual(rows[0]["remaining_5h_pct"], 100)
        self.assertEqual(rows[0]["remaining_week_pct"], 86)
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
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
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
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
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
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
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

    def test_reset_date_formats_are_supported(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        fixtures = [
            ("main1", [
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 21:51)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
            ], "Apr 22 16:51"),
            ("main2", [
                "Current session",
                "12% used",
                "Current week",
                "34% used",
                "Resets Thursday, April 17",
            ], "Apr 17"),
            ("main3", [
                "Current session",
                "12% used",
                "Current week",
                "34% used",
                "Resets April 17, 2026",
            ], "Apr 17"),
        ]

        for name, lines, expected in fixtures:
            provider = "claude" if lines[0].startswith("Current session") else "codex"
            service["create_session"](name, provider if provider == "claude" else "codex")
            root = os.path.join(temp_dir, "profiles", name, "claude-home" if provider == "claude" else "")
            session_log = os.path.join(root, "log", "cdx-session.log")
            os.makedirs(os.path.dirname(session_log), exist_ok=True)
            with open(session_log, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            rows = [row for row in service["get_status_rows"]() if row["session_name"] == name]
            self.assertEqual(rows[0]["reset_at"], expected)

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
        self.assertEqual(rows[0]["reset_at"], "Apr 17")

    def test_corrupted_sessions_json_raises(self):
        temp_dir = self.make_temp_dir()
        store_file = os.path.join(temp_dir, "sessions.json")
        os.makedirs(temp_dir, exist_ok=True)
        with open(store_file, "w", encoding="utf-8") as handle:
            handle.write("{bad json")
        store = create_session_store(temp_dir)
        with self.assertRaises(json.JSONDecodeError):
            store["list_sessions"]()

    def test_corrupted_state_file_fails_launch(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        state_path = os.path.join(temp_dir, "state", "main.json")
        with open(state_path, "w", encoding="utf-8") as handle:
            handle.write("{bad json")
        with self.assertRaises(json.JSONDecodeError):
            service["launch_session"]("main")


if __name__ == "__main__":
    unittest.main()
