import os
import tempfile
import unittest

from src.cli_commands import _read_handoff_transcript


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


if __name__ == "__main__":
    unittest.main()
