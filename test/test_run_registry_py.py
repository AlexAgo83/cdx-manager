import os
import shutil
import tempfile
import threading
import unittest

from src.run_registry import RunRegistry


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


if __name__ == "__main__":
    unittest.main()
