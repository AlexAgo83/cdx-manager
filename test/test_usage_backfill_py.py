import json
import os
import tempfile
import unittest

from src.session_service import create_session_service


class UsageBackfillTests(unittest.TestCase):
    def test_repair_backfills_only_the_exact_latest_claude_conversation(self):
        with tempfile.TemporaryDirectory() as base:
            service = create_session_service({"base_dir": base, "env": {}})
            session = service["create_session"]("tapion", provider="claude")
            session = service["launch_session"]("tapion")
            conversation = session["conversation"]
            project = os.path.join(session["authHome"], ".claude", "projects", "project")
            os.makedirs(project)
            path = os.path.join(project, f"{conversation['id']}.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5", "usage": {"input_tokens": 2, "cache_creation_input_tokens": 3, "cache_read_input_tokens": 5, "output_tokens": 7}}}) + "\n")
            service["record_launch_history"]("tapion", {"status": "success", "started_at": conversation["recordedAt"]})

            self.assertEqual(service["backfill_interactive_usage"](dry_run=True)["backfilled"], 1)
            self.assertIsNone(service["get_launch_history"]("tapion", limit=1)[0].get("usage"))
            self.assertEqual(service["backfill_interactive_usage"](dry_run=False)["backfilled"], 1)
            entry = service["get_launch_history"]("tapion", limit=1)[0]
            self.assertEqual(entry["usage"]["total_tokens"], 17)
            self.assertEqual(entry["usage_backfilled_reason"], "exact_current_conversation")

    def test_next_launch_backfills_the_previous_conversation(self):
        with tempfile.TemporaryDirectory() as base:
            service = create_session_service({"base_dir": base, "env": {}})
            session = service["create_session"]("tapion", provider="claude")
            session = service["launch_session"]("tapion")
            project = os.path.join(session["authHome"], ".claude", "projects", "project")
            os.makedirs(project)
            with open(os.path.join(project, f"{session['conversation']['id']}.jsonl"), "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 2, "output_tokens": 3}}}) + "\n")
            service["record_launch_history"]("tapion", {"status": "success", "started_at": session["conversation"]["recordedAt"]})

            service["launch_session"]("tapion")

            self.assertEqual(service["get_launch_history"]("tapion", limit=1)[0]["usage"]["total_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
