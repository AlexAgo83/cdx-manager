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
            events = []
            apply_update_all_plan(plan, service, env={"PATH": bin_dir}, runner=runner, progress=events.append)
            self.assertTrue(service["get_session"]("main")["launch"]["rtk"])
            self.assertEqual(events[0]["phase"], "start")
            self.assertEqual(events[-1]["phase"], "done")

    def test_failed_dependency_skips_plugin_install(self):
        calls = []

        def runner(command, **_kwargs):
            calls.append(command)
            return {"returncode": 2, "stdout": "", "stderr": "bad marketplace"}

        plan = {"steps": [
            {"id": "marketplace", "name": "add marketplace", "command": ["codex", "plugin", "marketplace", "add", "url"], "env": {}},
            {"name": "install plugin", "command": ["codex", "plugin", "add", "ponytail@ponytail"], "env": {}, "requires": "marketplace"},
        ]}
        results = apply_update_all_plan(plan, {}, env={}, runner=runner)
        self.assertEqual(calls, [["codex", "plugin", "marketplace", "add", "url"]])
        self.assertTrue(results[1]["skipped"])

    def test_ponytail_uses_cached_git_revision_when_config_has_no_revision(self):
        with tempfile.TemporaryDirectory(prefix="cdx-ponytail-") as root:
            auth_home = os.path.join(root, "profile")
            os.makedirs(os.path.join(auth_home, ".tmp", "marketplaces", "ponytail"))
            with open(os.path.join(auth_home, "config.toml"), "w", encoding="utf-8") as handle:
                handle.write('[marketplaces.ponytail]\nsource = "https://github.com/DietrichGebert/ponytail.git"\n')

            def runner(command, **_kwargs):
                if command[-2:] == ["rev-parse", "HEAD"]:
                    return {"returncode": 0, "stdout": "a" * 40, "stderr": ""}
                return {"returncode": 1, "stdout": "", "stderr": ""}

            from src.update_all import _ponytail_revision
            self.assertEqual(_ponytail_revision(auth_home, env={}, runner=runner), "a" * 40)
