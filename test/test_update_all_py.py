import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from src.session_service import create_session_service
from src.update_all import apply_update_all_plan, collect_update_all_plan


class UpdateAllTests(unittest.TestCase):
    @mock.patch("src.update_all._fetch_json", return_value={})
    def test_plan_enables_rtk_only_after_apply(self, _fetch):
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


class OfficialSourceTests(unittest.TestCase):
    def plan(self, versions, payload, help_text="", failure=None):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            self.assertLessEqual(kwargs["timeout"], 5)
            if command[-1] == "--version":
                value = versions[command[0]]
                return {"returncode": 0, "stdout": value, "stderr": ""}
            return {"returncode": 0, "stdout": help_text, "stderr": ""}

        with mock.patch("src.update_all._which", side_effect=lambda command, env: f"/bin/{command}" if command in versions else None), \
             mock.patch("src.update_all._fetch_json", return_value=payload, side_effect=failure) as fetch:
            plan = collect_update_all_plan({"list_sessions": lambda: []}, env={"PATH": "/fake"}, runner=runner)
        return plan, calls, fetch

    def test_each_official_source_matches_and_preserves_json_fields(self):
        sources = [
            ("claude", {"version": "1.2.3"}, "registry.npmjs.org/@anthropic-ai/claude-code/latest"),
            ("codex", {"version": "1.2.3"}, "registry.npmjs.org/@openai/codex/latest"),
            ("rtk", {"tag_name": "v1.2.3"}, "api.github.com/repos/rtk-ai/rtk/releases/latest"),
            ("agy", [{"version": "1.2.3"}], "antigravity-auto-updater"),
            ("ollama", {"url": "https://github.com/ollama/ollama/releases/download/v1.2.3/Ollama.zip"}, "ollama.com/api/update?"),
        ]
        for command, payload, url in sources:
            with self.subTest(command=command):
                plan, calls, fetch = self.plan({command: "1.2.3"}, payload)
                item = next(item for item in plan["items"] if item["installed"])
                self.assertEqual(item["status"], "up_to_date")
                self.assertEqual(item["latest_version"], "1.2.3")
                self.assertIn("update_command", json.loads(json.dumps(item)))
                self.assertIn(url, fetch.call_args.args[0])
                self.assertEqual(calls, [[command, "--version"]])
                self.assertEqual(plan["steps"], [])

    def test_outdated_claude_and_antigravity_use_advertised_native_updater(self):
        for command, payload in [("claude", {"version": "2.1.316"}), ("agy", [{"version": "2.1.316"}])]:
            with self.subTest(command=command):
                plan, calls, _ = self.plan({command: "2.1.228"}, payload, "Commands:\n  update [options]  Update to latest version\n")
                item = next(item for item in plan["items"] if item["installed"])
                self.assertEqual(item["status"], "update_available")
                self.assertEqual(item["update_command"], [command, "update"])
                self.assertNotIn([command, "update"], calls)
                applied = []
                def runner(argv, applied=applied, **kwargs):
                    applied.append(argv)
                    return {"returncode": 0, "stdout": "", "stderr": ""}
                apply_update_all_plan(plan, {}, runner=runner)
                self.assertEqual(applied, [[command, "update"]])

    def test_outdated_without_native_updater_never_guesses_install(self):
        for command, payload in [("rtk", {"tag_name": "v1.1.0"}), ("agy", [{"version": "1.1.0"}]),
                                 ("ollama", {"url": "https://github.com/ollama/ollama/releases/download/v1.1.0/Ollama.zip"})]:
            plan, _, _ = self.plan({command: "0.45.0"}, payload)
            item = next(item for item in plan["items"] if item["installed"])
            self.assertEqual(item["status"], "update_available")
            self.assertIsNone(item["update_command"])
            self.assertIn("No supported", item["reason"])
            self.assertEqual(plan["steps"], [])

    def test_source_failures_are_unknown_even_with_brew_available(self):
        for command in ("codex", "claude", "agy", "ollama", "rtk"):
            for error in (TimeoutError("timeout"), OSError("offline"), ValueError("invalid JSON")):
                with self.subTest(command=command, error=error):
                    plan, _, _ = self.plan({command: "1.2.3"}, {}, failure=error)
                    item = next(item for item in plan["items"] if item["installed"])
                    self.assertEqual(item["status"], "unknown")
                    self.assertIsNone(item["latest_version"])
                    self.assertEqual(plan["steps"], [])

    def test_missing_tools_do_not_query_sources(self):
        plan, calls, fetch = self.plan({}, {})
        self.assertEqual(calls, [])
        fetch.assert_not_called()
        for item in plan["items"]:
            self.assertFalse(item["installed"])
            self.assertEqual(item["status"], "not_installed")
            self.assertIsNone(item["version"])
            self.assertIsNone(item["latest_version"])
            self.assertIsNone(item["update_command"])

    def test_missing_or_ahead_installed_version_is_unknown(self):
        for current in ("unrecognized", "9.0.0", "1.2.3-beta"):
            plan, _, _ = self.plan({"claude": current}, {"version": "1.2.3"})
            self.assertEqual(plan["items"][1]["status"], "unknown")

    def test_failed_version_and_help_probes_are_not_trusted(self):
        from src.update_all import _native_update_command, _version
        runner = lambda *args, **kwargs: {"returncode": 1, "stdout": "2.1.316\n  update  Update", "stderr": ""}
        self.assertIsNone(_version("claude", {}, runner))
        self.assertIsNone(_native_update_command("claude", "claude", "/bin/claude", {"PATH": "/missing"}, runner))
        timeout = mock.Mock(side_effect=subprocess.TimeoutExpired("claude", 5))
        self.assertIsNone(_version("claude", {}, timeout))

    def test_ollama_uses_client_version_instead_of_server_version(self):
        from src.update_all import _version
        runner = lambda *args, **kwargs: {"returncode": 0, "stdout": "ollama version is 0.9.0\nWarning: client version is 0.8.0", "stderr": ""}
        self.assertEqual(_version("ollama", {}, runner), "0.8.0")

    def test_ponytail_failed_source_is_unknown(self):
        sessions = [{"name": "main", "provider": "codex", "authHome": "/fake"}]
        with mock.patch("src.update_all._which", return_value=None), \
             mock.patch("src.update_all._ponytail_revision", return_value="a" * 40):
            plan = collect_update_all_plan({"list_sessions": lambda: sessions}, env={"PATH": "/fake"},
                                           runner=lambda *args, **kwargs: {"returncode": 1, "stdout": "", "stderr": "offline"})
        self.assertEqual(plan["setup"]["ponytail"][0]["status"], "unknown")
        self.assertIsNone(plan["setup"]["ponytail"][0]["latest_revision"])

    def test_http_probe_is_read_only_and_bounded(self):
        from src.update_all import _fetch_json
        with mock.patch("src.update_all.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b'{"version":"1.2.3"}'
            self.assertEqual(_fetch_json("https://registry.npmjs.org/@anthropic-ai/claude-code/latest"), {"version": "1.2.3"})
            request = urlopen.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    def test_only_verified_brew_path_is_upgraded(self):
        from src.update_all import _native_update_command
        with mock.patch("src.update_all.os.path.realpath", return_value="/opt/homebrew/Caskroom/claude-code/1.0.0/claude"), \
             mock.patch("src.update_all._which", return_value="/opt/homebrew/bin/brew"):
            self.assertEqual(_native_update_command("claude", "claude", "/bin/claude", {}, None),
                             ["brew", "upgrade", "--cask", "claude-code"])

    def test_malformed_sources_never_become_up_to_date(self):
        for payload in ({}, [], None, {"version": "garbage"}, {"tag_name": "v1.2.3", "prerelease": True}):
            for command in ("claude", "rtk", "agy", "ollama"):
                plan, _, _ = self.plan({command: "1.2.3"}, payload)
                self.assertEqual(next(item for item in plan["items"] if item["installed"])["status"], "unknown")
