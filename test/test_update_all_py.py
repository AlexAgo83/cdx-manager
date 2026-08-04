import os
import tempfile
import unittest

from src.session_service import create_session_service
from src.update_all import apply_update_all_plan, collect_update_all_plan


class UpdateAllTests(unittest.TestCase):
    def test_plan_enables_rtk_only_after_apply(self):
        with tempfile.TemporaryDirectory(prefix="cdx-update-all-") as root:
            service = create_session_service({"base_dir": root})
            service["create_session"]("main")

            def runner(command, **_kwargs):
                if command[:3] == ["brew", "outdated", "--json=v2"]:
                    return {"returncode": 0, "stdout": '{"formulae": [], "casks": []}', "stderr": ""}
                if command[-1:] == ["--version"]:
                    return {"returncode": 0, "stdout": "1.2.3", "stderr": ""}
                return {"returncode": 0, "stdout": "", "stderr": ""}

            bin_dir = os.path.join(root, "bin")
            os.mkdir(bin_dir)
            for name in ("brew", "codex", "rtk"):
                path = os.path.join(bin_dir, name)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("#!/bin/sh\n")
                os.chmod(path, 0o755)
            plan = collect_update_all_plan(service, env={"PATH": bin_dir}, runner=runner)
            self.assertEqual(plan["setup"]["rtk_missing_sessions"], ["main"])
            self.assertNotIn("rtk", service["get_session"]("main").get("launch") or {})
            apply_update_all_plan(plan, service, env={"PATH": bin_dir}, runner=runner)
            self.assertTrue(service["get_session"]("main")["launch"]["rtk"])
