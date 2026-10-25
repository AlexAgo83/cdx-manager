"""Labelled runs, and a cap on how many run at once."""

import os
import tempfile
import unittest
from unittest import mock

from src.cli_args import _parse_run_args
from src.commands.runs import _detached_child_argv
from src.errors import CdxError
from src.run_registry import RunRegistry


def _start(registry, run_id, **extra):
    return registry.start(run_id, kind="assistant", session="work", provider="claude", model=None,
                          cwd="/repo", **extra)


class RunCapTests(unittest.TestCase):
    def setUp(self):
        self.registry = RunRegistry(tempfile.mkdtemp())
        alive = mock.patch("src.run_registry._is_pid_alive", return_value=True)
        alive.start()
        self.addCleanup(alive.stop)

    def test_the_cap_refuses_a_run_beyond_it(self):
        _start(self.registry, "a", max_parallel=2)
        _start(self.registry, "b", max_parallel=2)
        with self.assertRaises(CdxError) as raised:
            _start(self.registry, "c", max_parallel=2)
        self.assertEqual(raised.exception.code, "too_many_runs")
        _start(self.registry, "c")  # no cap, no refusal

    def test_a_run_rewritten_under_its_own_id_does_not_count_against_itself(self):
        _start(self.registry, "a", max_parallel=1)
        _start(self.registry, "a", max_parallel=1)

    def test_the_label_is_recorded_and_handed_to_a_detached_child(self):
        record = _start(self.registry, "a", label="fix build cts")
        self.assertEqual(record["label"], "fix build cts")
        argv = _detached_child_argv({"label": "fix build cts"}, "/p.txt", "work", "/repo")
        self.assertEqual(argv[argv.index("--label") + 1], "fix build cts")

    def test_max_parallel_must_be_a_positive_whole_number(self):
        base = ["work", "--cwd", os.getcwd(), "--prompt", "go", "--json"]
        self.assertEqual(_parse_run_args(base + ["--max-parallel", "2"])["max_parallel"], 2)
        with self.assertRaises(CdxError):
            _parse_run_args(base + ["--max-parallel", "0"])


if __name__ == "__main__":
    unittest.main()
