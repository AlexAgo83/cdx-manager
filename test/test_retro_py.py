"""Session retrospectives: started at session end, read with cdx retro."""

import json
import os
import tempfile
import unittest

from src import retro


class RetroTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.transcript = os.path.join(self.dir, "t.jsonl")
        with open(self.transcript, "w", encoding="utf-8") as handle:
            handle.write('{"type":"user","message":{"content":"do it"}}\n' * retro.MIN_USER_PROMPTS)
        self.calls = []
        self.session = {"name": "work", "provider": "claude", "launch": {"retro": True}}

    def _popen(self, argv, **kwargs):
        self.calls.append((argv, kwargs))

    def test_a_long_session_starts_a_read_only_detached_retro(self):
        argv = retro.start(self.session, "/repo", self.transcript, env={"CDX_BIN": "/bin/cdx"}, popen=self._popen)
        self.assertEqual(argv[:4], ["/bin/cdx", "run", "--provider", "claude"])
        for flag, value in (("--kind", "retro"), ("--permission", "read-only"), ("--power", "low"), ("--cwd", "/repo")):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn("--detach", argv)
        self.assertIn(self.transcript, argv[argv.index("--prompt") + 1])
        self.assertEqual(self.calls[0][1]["env"]["CDX_RETRO"], "1")

    def test_no_retro_when_off_short_or_already_a_retro(self):
        off = {**self.session, "launch": {}}
        short = os.path.join(self.dir, "short.jsonl")
        with open(short, "w", encoding="utf-8") as handle:
            handle.write('{"type":"user","message":{"content":"' + "x" * 300_000 + '"}}\n')
            handle.write('{"type":"user","message":{"content":[{"type":"tool_result"}]}}\n' * 5)
        self.assertIsNone(retro.start(off, "/repo", self.transcript, popen=self._popen))
        self.assertIsNone(retro.start(self.session, "/repo", short, popen=self._popen))
        self.assertIsNone(retro.start(self.session, "/repo", self.transcript, env={"CDX_RETRO": "1"}, popen=self._popen))
        self.assertEqual(self.calls, [])

    def test_reports_read_the_result_of_finished_retro_runs(self):
        stdout = os.path.join(self.dir, "out.json")
        with open(stdout, "w", encoding="utf-8") as handle:
            json.dump({"result": "## Verdict\nnothing to learn"}, handle)

        class Registry:
            def list(self, limit=20):
                return [{"run_id": "a", "kind": "assistant"},
                        {"run_id": "b", "kind": "retro", "status": "succeeded", "final_payload": {"stdout_path": stdout}}]

        (report,) = retro.reports(Registry())
        self.assertEqual(report["run_id"], "b")
        self.assertIn("nothing to learn", report["report"])


if __name__ == "__main__":
    unittest.main()
