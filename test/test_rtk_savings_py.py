"""rtk savings in cdx stats, read through rtk itself from every history it wrote."""

import json
import os
import tempfile
import unittest
from subprocess import CompletedProcess
from unittest import mock

from src import provider_runtime, rtk_savings


class RtkSavingsTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.shared = os.path.join(self.base, "shared.db")
        self.profile = os.path.join(self.base, "profiles", "work", "claude-home", "Library", "Application Support", "rtk", "history.db")
        os.makedirs(os.path.dirname(self.profile))
        for path in (self.shared, self.profile):
            open(path, "w").close()
        patch = mock.patch.object(rtk_savings, "operator_rtk_history_path", return_value=self.shared)
        patch.start()
        self.addCleanup(patch.stop)
        self.days = {
            self.shared: [{"date": "2026-10-20", "commands": 10, "input_tokens": 1000, "saved_tokens": 400}],
            self.profile: [{"date": "2026-09-01", "commands": 5, "input_tokens": 100, "saved_tokens": 50},
                           {"date": "2026-10-21", "commands": 2, "input_tokens": 200, "saved_tokens": 100}],
        }

    def _run(self, argv, env=None, **kwargs):
        return CompletedProcess(argv, 0, json.dumps({"daily": self.days[env["RTK_DB_PATH"]]}), "")

    def test_every_history_is_summed_over_the_period(self):
        with mock.patch.object(rtk_savings.shutil, "which", return_value="/bin/rtk"):
            totals = rtk_savings.rtk_saved(self.base, {"from": "2026-10-01T00:00:00+01:00"}, run=self._run)
        self.assertEqual(totals, {"commands": 12, "input_tokens": 1200, "saved_tokens": 500, "databases": 2})

    def test_no_rtk_means_no_figure(self):
        with mock.patch.object(rtk_savings.shutil, "which", return_value=None):
            self.assertIsNone(rtk_savings.rtk_saved(self.base, run=self._run))

    def test_an_operator_chosen_history_comes_first(self):
        chosen = os.path.join(self.base, "chosen.db")
        open(chosen, "w").close()
        found = rtk_savings.history_databases(self.base, {"RTK_DB_PATH": chosen})
        self.assertEqual(found, [chosen, self.profile])


@unittest.skipIf(os.name == "nt", "passwd lookup is POSIX only")
class OperatorRtkHistoryPathTests(unittest.TestCase):
    def test_a_uid_without_passwd_entry_falls_back_to_home(self):
        import pwd

        with mock.patch.object(pwd, "getpwuid", side_effect=KeyError("uid")), \
                mock.patch.object(provider_runtime.sys, "platform", "linux"):
            path = provider_runtime.operator_rtk_history_path({"HOME": "/home/me"})
        self.assertEqual(path, os.path.join("/home/me", ".local", "share", "rtk", "history.db"))

    def test_linux_honours_xdg_data_home(self):
        with mock.patch.object(provider_runtime.sys, "platform", "linux"):
            path = provider_runtime.operator_rtk_history_path({"XDG_DATA_HOME": "/data"})
        self.assertEqual(path, os.path.join("/data", "rtk", "history.db"))


if __name__ == "__main__":
    unittest.main()
