"""A session started on a task, told what the user's go-ahead covers."""

import unittest

from src.commands.launch import _parse_launch_args
from src.errors import CdxError


class LaunchTaskTests(unittest.TestCase):
    def test_task_and_end_state_become_the_first_message(self):
        _dir, _rest, prompt = _parse_launch_args(["--task", "Fix CI", "--end-state", "CI green, PR merged"])
        self.assertTrue(prompt["prompt"].startswith("Task: Fix CI"))
        self.assertIn("End state: CI green, PR merged", prompt["prompt"])
        self.assertIn("without asking again", prompt["prompt"])

    def test_a_task_without_end_state_stops_before_publishing(self):
        _dir, _rest, prompt = _parse_launch_args(["--task", "Fix CI"])
        self.assertIn("stop and show the result before any commit, push or pull request", prompt["prompt"])

    def test_task_does_not_mix_with_a_prompt_and_end_state_needs_a_task(self):
        with self.assertRaises(CdxError):
            _parse_launch_args(["--task", "a", "--prompt", "b"])
        with self.assertRaises(CdxError):
            _parse_launch_args(["--end-state", "merged"])


if __name__ == "__main__":
    unittest.main()
