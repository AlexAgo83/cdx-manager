"""Ollama token counts, parsed from the PTY capture cdx already takes.

The sample below is real: captured from `script -q -F log ollama run
smollm2:135m --verbose "say hi"` on ollama 0.32.11, escapes and all. It is not
hand-authored, because the point of the exercise was that nobody had confirmed
the format.
"""

import os
import tempfile
import unittest

from src.interactive_usage import (
    MATCH_RUN_TRANSCRIPT,
    _ollama_usage,
    extract_interactive_usage,
)

REAL_CAPTURE = '[?25l\x1b[?25h week\x1b[?25l\x1b[?25h of\x1b[?25l\x1b[?25h February\x1b[?25l\x1b[?25h \x1b[?25l\x1b[?25h1\x1b[?25l\x1b[?25h8\x1b[?25l\x1b[?25hth\x1b[?25l\x1b[?25h.\x1b[?25l\x1b[?25h How\x1b[?25l\x1b[?25h can\x1b[?25l\x1b[?25h I\x1b[?25l\x1b[?25h help\x1b[?25l\x1b[?25h you\x1b[?25l\x1b[?25h \x1b[K\r\ntoday\x1b[?25l\x1b[?25h?\x1b[?25l\x1b[?25h Are\x1b[?25l\x1b[?25h you\x1b[?25l\x1b[?25h studying\x1b[?25l\x1b[?25h,\x1b[?25l\x1b[?25h or\x1b[?25l\x1b[?25h just\x1b[?25l\x1b[?25h looking\x1b[?25l\x1b[?25h to\x1b[?25l\x1b[?25h learn\x1b[?25l\x1b[?25h more\x1b[?25l\x1b[?25h about\x1b[?25l\x1b[?25h the\x1b[?25l\x1b[?25h world\x1b[?25l\x1b[?25h?\x1b[?25l\x1b[?25h\r\n\r\ntotal duration:       1.159523666s\r\nload duration:        825.329083ms\r\nprompt eval count:    32 token(s)\r\nprompt eval duration: 101.189ms\r\nprompt eval rate:     316.24 tokens/s\r\neval count:           58 token(s)\r\neval duration:        228.427ms\r\neval rate:            253.91 tokens/s\r\n\x1b[?25l\x1b[?25h'


class OllamaUsageTests(unittest.TestCase):
    def _read(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cdx-session.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            with open(path, encoding="utf-8") as handle:
                return _ollama_usage(handle)

    def test_the_real_capture_yields_its_token_counts(self):
        usage, model = self._read(REAL_CAPTURE)
        self.assertEqual(usage["input_tokens"], 32)
        self.assertEqual(usage["output_tokens"], 58)
        self.assertEqual(usage["total_tokens"], 90)
        # Ollama runs locally against no prompt cache and reports no reasoning.
        self.assertIsNone(usage["cached_input_tokens"])
        self.assertIsNone(usage["reasoning_tokens"])
        # No model: local models are in no price table, and naming one would
        # invite pricing something that is free.
        self.assertIsNone(model)

    def test_escape_sequences_do_not_defeat_the_match(self):
        # The capture carries cursor show/hide sequences between individual
        # words and carriage returns overwriting lines. A parser that only
        # works on cleaned text is one that fails in production.
        self.assertIn("\x1b[?25l", REAL_CAPTURE)
        self.assertIn("\r", REAL_CAPTURE)
        self.assertIsNotNone(self._read(REAL_CAPTURE)[0])

    def test_each_response_contributes_a_block_and_they_sum(self):
        usage, _model = self._read(REAL_CAPTURE + REAL_CAPTURE)
        self.assertEqual(usage["input_tokens"], 64)
        self.assertEqual(usage["output_tokens"], 116)

    def test_a_capture_without_the_block_is_absence_not_an_error(self):
        usage, _model = self._read("some terminal output, no stats block\n")
        self.assertIsNone(usage)

    def test_a_changed_format_degrades_to_absence(self):
        usage, _model = self._read("prompt eval count: lots of tokens\neval count: many\n")
        self.assertIsNone(usage)


class OllamaResolutionTests(unittest.TestCase):
    def test_the_runs_own_capture_is_the_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cdx-session.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(REAL_CAPTURE)

            usage, selected, match, _model = extract_interactive_usage(
                "ollama", None, None, None, path)

            self.assertEqual(selected, path)
            self.assertEqual(match, MATCH_RUN_TRANSCRIPT)
            self.assertEqual(usage["output_tokens"], 58)

    def test_no_capture_means_no_usage_rather_than_a_scan(self):
        # There is no provider directory to fall back to, and inventing one
        # would repeat the mistake the claude/codex path just stopped making.
        self.assertEqual(
            extract_interactive_usage("ollama", "/tmp/nowhere", None, None, None),
            (None, None, None, None),
        )


if __name__ == "__main__":
    unittest.main()
