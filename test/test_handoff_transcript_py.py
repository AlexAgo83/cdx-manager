import os
import tempfile
import unittest

from src.cli_commands import _latest_handoff_transcript_path, _read_handoff_transcript


class ReadHandoffTranscriptTest(unittest.TestCase):
    def _write_log(self, text):
        fd, path = tempfile.mkstemp(suffix=".log")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_strips_ansi_and_control_noise_from_script_log(self):
        # Typical `script`-captured TUI frame: CSI color, cursor move, OSC title,
        # carriage-return repaint. Only the human text should survive.
        noisy = (
            "\x1b[2J\x1b[H\x1b]0;claude\x07"
            "\x1b[32mUser:\x1b[0m fix the bug\r"
            "\x1b[1;5HAssistant: done\x1b[K\n"
        )
        path = self._write_log(noisy)
        content, truncated = _read_handoff_transcript(path)
        self.assertFalse(truncated)
        self.assertNotIn("\x1b", content)
        self.assertIn("fix the bug", content)
        self.assertIn("Assistant: done", content)

    def test_prefers_native_jsonl_and_excludes_tool_records(self):
        with tempfile.TemporaryDirectory(prefix="cdx-handoff-") as root:
            auth_home = os.path.join(root, "profile")
            log_dir = os.path.join(auth_home, "log")
            session_dir = os.path.join(auth_home, "sessions", "2026", "08", "04")
            os.makedirs(log_dir)
            os.makedirs(session_dir)
            with open(os.path.join(log_dir, "cdx-session.log"), "w", encoding="utf-8") as handle:
                handle.write("noisy terminal output\n")
            native = os.path.join(session_dir, "rollout.jsonl")
            with open(native, "w", encoding="utf-8") as handle:
                handle.write('{"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Finish the migration"}]}}\n')
                handle.write('{"type":"response_item","payload":{"type":"function_call","name":"exec","arguments":"very noisy output"}}\n')
                handle.write('{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Next: run tests"}]}}\n')
            session = {"authHome": auth_home, "sessionRoot": auth_home}
            self.assertEqual(_latest_handoff_transcript_path(session), native)
            content, truncated = _read_handoff_transcript(native)
            self.assertFalse(truncated)
            self.assertIn("[user]\nFinish the migration", content)
            self.assertIn("[assistant]\nNext: run tests", content)
            self.assertNotIn("noisy", content)


if __name__ == "__main__":
    unittest.main()
