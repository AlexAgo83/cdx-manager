import os
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from src.errors import CdxError
from src.run_registry import RunRegistry, _acquire_posix_lock


class RunRegistryTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp(prefix="cdx-registry-test-")
        self.addCleanup(shutil.rmtree, self.base_dir, True)
        self.registry = RunRegistry(self.base_dir)

    def _start(self, run_id):
        return self.registry.start(
            run_id,
            kind="assistant",
            session="work",
            provider="codex",
            model=None,
            cwd=self.base_dir,
        )

    def test_migrate_keeps_one_run_and_records_the_session_sequence(self):
        registry = RunRegistry(self.base_dir)
        registry.start("r1", kind="assistant", session="work1", provider="codex", model=None, cwd=self.base_dir)

        registry.migrate("r1", session="work2", provider="codex", reason="rate_limited")
        registry.migrate("r1", session="oss", provider="claude", reason="rate_limited")
        registry.finish("r1", status="succeeded")

        runs = registry.list(limit=10)
        self.assertEqual(len(runs), 1)
        run = runs[0]
        # Top-level session/provider name the current occupant, so readers that
        # know nothing about occupancies stay correct.
        self.assertEqual(run["session"], "oss")
        self.assertEqual(run["provider"], "claude")
        self.assertEqual(
            [(item["session"], item["reason"]) for item in run["occupancies"]],
            [("work1", "rate_limited"), ("work2", "rate_limited"), ("oss", "succeeded")],
        )
        self.assertTrue(all(item["ended_at"] for item in run["occupancies"]))

    def test_a_run_that_never_migrates_still_records_one_occupancy(self):
        registry = RunRegistry(self.base_dir)
        registry.start("r2", kind="assistant", session="work1", provider="codex", model=None, cwd=self.base_dir)
        registry.finish("r2", status="failed")

        run = registry.get("r2")
        self.assertEqual(len(run["occupancies"]), 1)
        self.assertEqual(run["occupancies"][0]["session"], "work1")
        self.assertEqual(run["occupancies"][0]["reason"], "failed")

    def test_in_flight_run_is_not_marked_stale(self):
        record = self._start("run-1")
        self.assertEqual(record["pid"], os.getpid())
        listed = self.registry.list()
        self.assertEqual(listed[0]["status"], "running")

    def test_run_with_dead_pid_is_marked_stale(self):
        self._start("run-1")
        data_path = self.registry.path
        import json

        with open(data_path, encoding="utf-8") as handle:
            data = json.load(handle)
        data["runs"][0]["pid"] = 2 ** 22 + 12345  # beyond default pid_max
        with open(data_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        listed = self.registry.list()
        self.assertEqual(listed[0]["status"], "stale")
        self.assertEqual(listed[0]["error"]["code"], "stale_process")

    def _finish_at(self, run_id, ended_at):
        self._start(run_id)
        self.registry.finish(run_id, status="succeeded")
        import json

        with open(self.registry.path, encoding="utf-8") as handle:
            data = json.load(handle)
        for run in data["runs"]:
            if run["run_id"] == run_id:
                run["ended_at"] = ended_at
        with open(self.registry.path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def test_since_selects_only_runs_completed_after_the_cursor(self):
        self._finish_at("old", "2026-08-07T10:00:00Z")
        self._finish_at("new", "2026-08-07T12:00:00Z")
        cursor = datetime(2026, 8, 7, 11, 0, 0, tzinfo=timezone.utc)

        listed = self.registry.list(since=cursor)

        self.assertEqual([run["run_id"] for run in listed], ["new"])

    def test_since_returns_everything_after_the_cursor_ignoring_limit(self):
        for index in range(25):
            self._finish_at(f"run-{index:02d}", f"2026-08-07T12:{index:02d}:00Z")
        cursor = datetime(2026, 8, 7, 11, 0, 0, tzinfo=timezone.utc)

        # A cursor caller asks "what finished since I last looked". Truncating
        # that to a row count is the silent miss the cursor exists to remove:
        # a watchdog more than `limit` completions behind would never see the
        # older ones at all.
        self.assertEqual(len(self.registry.list(limit=5, since=cursor)), 25)
        self.assertEqual(len(self.registry.list(limit=5)), 5)

    def test_since_excludes_runs_that_have_not_completed(self):
        self._start("in-flight")
        cursor = datetime(2020, 1, 1, tzinfo=timezone.utc)

        self.assertEqual(self.registry.list(since=cursor), [])

    def test_since_ignores_records_with_an_unparseable_end_time(self):
        self._finish_at("broken", "not-a-timestamp")
        cursor = datetime(2020, 1, 1, tzinfo=timezone.utc)

        # Reporting it would re-announce the same corrupt row on every poll.
        self.assertEqual(self.registry.list(since=cursor), [])

    def test_concurrent_starts_do_not_lose_records(self):
        errors = []

        def worker(index):
            try:
                self._start(f"run-{index}")
            except Exception as exc:  # pragma: no cover - surfaced via assert
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        listed = self.registry.list(limit=50)
        self.assertEqual(len(listed), 20)

    def test_contention_waits_instead_of_failing(self):
        """Twenty parallel writers is the load cdx exists to carry.

        On Windows this used to raise OSError(36) once `LK_LOCK`'s ten fixed
        attempts ran out, while POSIX `flock` simply waited - the same
        contention producing an error on one platform and a wait on the other.
        Reproduced on a physical machine; CI never showed it, being less
        contended than a real desktop.
        """
        errors = []

        def worker(index):
            try:
                self._start(f"contend-{index}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len({run["run_id"] for run in self.registry.list(limit=50)}), 20)

    def test_an_exhausted_wait_is_reported_as_contention_not_as_an_oserror(self):
        """Bounded on purpose: an unbounded wait would hang every later command
        behind a stuck holder, with nothing to report."""
        from src.run_registry import _acquire_windows_lock

        class NeverFree:
            def seek(self, _pos): pass
            def fileno(self): return -1

        with mock.patch("src.run_registry.time.sleep"):
            with mock.patch.dict("sys.modules", {"msvcrt": mock.Mock(
                LK_NBLCK=1, locking=mock.Mock(side_effect=OSError(36, "Resource deadlock avoided")),
            )}):
                with self.assertRaises(CdxError) as caught:
                    _acquire_windows_lock(NeverFree(), timeout_seconds=0)

        self.assertIn("run registry lock", str(caught.exception))
        self.assertEqual(caught.exception.exit_code, 75)

    def test_windows_locks_without_blocking_and_waits_in_our_own_loop(self):
        """The non-blocking form on purpose.

        `LK_LOCK` does its own waiting - ten attempts, one second apart, then
        EDEADLOCK - which is a budget cdx cannot extend or report on. Taking
        `LK_NBLCK` and looping here makes the wait bounded by a deadline cdx
        chooses and lets an exhausted wait be named.
        """
        calls = []
        fake_msvcrt = SimpleNamespace(
            LK_NBLCK=3,
            LK_UNLCK=2,
            locking=lambda fd, mode, length: calls.append((mode, length)),
        )
        with mock.patch("src.run_registry.sys.platform", "win32"):
            with mock.patch.dict("sys.modules", {"msvcrt": fake_msvcrt}):
                self._start("run-1")

        self.assertEqual(calls, [(3, 1), (2, 1)])

    def test_posix_lock_timeout_is_actionable(self):
        class NeverFree:
            pass

        fake_fcntl = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=mock.Mock(side_effect=BlockingIOError()))
        with mock.patch("src.run_registry.time.sleep"):
            with mock.patch.dict("sys.modules", {"fcntl": fake_fcntl}):
                with self.assertRaises(CdxError) as caught:
                    _acquire_posix_lock(NeverFree(), timeout_seconds=0)

        self.assertIn("run registry lock", str(caught.exception))
        self.assertEqual(caught.exception.exit_code, 75)


if __name__ == "__main__":
    unittest.main()
