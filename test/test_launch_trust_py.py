"""Folder trust and hook approvals recorded before a provider starts."""

import json
import os
import queue
import shutil
import tempfile
import unittest
from unittest import mock

from cli_test_support import CliTestBase, _AuthHarness

from src.cli import main
from src.cli_args import _parse_set_args, _parse_unset_args
from src.launch_trust import _trust_codex, claude_project_key, ensure_trusted, trust_paths
from src.session_service import create_session_service


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)


class _FakeAppServer:
    """A `codex app-server` stand-in that answers each request as it is written.

    It keeps the config it is told to write and derives `trustStatus` from it,
    so a second pass sees what the first one approved.
    """

    def __init__(self, hooks, trusted_projects=()):
        self.hooks = hooks
        self.projects = {path: {"trust_level": "trusted"} for path in trusted_projects}
        self.state = {}
        self.config = {}
        self.requests = []
        self.argv = None
        self.env = None

    def __call__(self, argv, **kwargs):
        self.argv, self.env = argv, kwargs["env"]
        server, lines = self, queue.Queue()

        class Stdin:
            def write(self, text):
                message = json.loads(text)
                server.requests.append(message)
                lines.put(json.dumps({"id": message["id"], "result": server.answer(message)}) + "\n")

            def flush(self):
                pass

        class Process:
            stdin = Stdin()
            stdout = iter(lines.get, None)

            def terminate(self):
                lines.put(None)

            def wait(self, timeout=None):
                return 0

        return Process()

    def answer(self, message):
        params = message.get("params") or {}
        if message["method"] == "config/batchWrite":
            for edit in params["edits"]:
                if edit["keyPath"] == "projects":
                    self.projects.update(edit["value"])
                elif edit["keyPath"] == "hooks.state":
                    self.state.update(edit["value"])
                else:
                    self.config[edit["keyPath"]] = edit["value"]
            return {"status": "ok"}
        if message["method"] == "hooks/list":
            listed = []
            for key, current in self.hooks.items():
                stored = self.state.get(key)
                if stored is None:
                    status = "untrusted"
                else:
                    joined = "/".join(filter(None, (stored["trusted_hash"], stored.get("trusted_content_hash"))))
                    status = "trusted" if joined == current else "modified"
                listed.append({"key": key, "currentHash": current, "trustStatus": status})
            return {"data": [{"cwd": params["cwds"][0], "hooks": listed, "warnings": [], "errors": []}]}
        return {}

    def methods(self):
        return [request["method"] for request in self.requests]


class LaunchTrustTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.folder = os.path.join(self.root, "project")
        os.makedirs(self.folder)
        self.home = os.path.join(self.root, "profiles", "work", "home")
        self.other_home = os.path.join(self.root, "profiles", "other", "home")
        os.makedirs(self.home)
        os.makedirs(self.other_home)

    def session(self, provider, **launch):
        return {"name": "work", "provider": provider, "authHome": self.home, "launch": launch}

    def test_claude_trust_keeps_every_other_setting_and_project(self):
        path = os.path.join(self.home, ".claude.json")
        _write(path, {"oauthAccount": {"emailAddress": "a@example.com"}, "numStartups": 4,
                      "projects": {"/elsewhere": {"hasTrustDialogAccepted": False, "allowedTools": ["Read"]},
                                   claude_project_key(self.folder): {"allowedTools": ["Bash"], "lastCost": 1.5}}})
        other = os.path.join(self.other_home, ".claude.json")
        _write(other, {"projects": {}})

        self.assertIsNone(ensure_trusted(self.session("claude"), self.folder))

        document = _read(path)
        self.assertEqual(document["oauthAccount"], {"emailAddress": "a@example.com"})
        self.assertEqual(document["numStartups"], 4)
        self.assertEqual(document["projects"]["/elsewhere"], {"hasTrustDialogAccepted": False, "allowedTools": ["Read"]})
        self.assertEqual(document["projects"][claude_project_key(self.folder)],
                         {"allowedTools": ["Bash"], "lastCost": 1.5, "hasTrustDialogAccepted": True})
        self.assertEqual(_read(other), {"projects": {}})

    def test_claude_trust_is_idempotent_and_creates_a_missing_config(self):
        session = self.session("claude")
        self.assertIsNone(ensure_trusted(session, self.folder))
        self.assertTrue(_read(os.path.join(self.home, ".claude.json"))["projects"][claude_project_key(self.folder)]["hasTrustDialogAccepted"])
        with mock.patch("src.launch_trust._write_json") as write:
            self.assertIsNone(ensure_trusted(session, self.folder))
        write.assert_not_called()

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlinked_folder_is_trusted_under_both_spellings(self):
        link = os.path.join(self.root, "link")
        os.symlink(self.folder, link)
        self.assertEqual(trust_paths(link), [link, os.path.realpath(self.folder)])
        ensure_trusted(self.session("antigravity"), link)
        settings = _read(os.path.join(self.home, ".gemini", "antigravity-cli", "settings.json"))
        self.assertEqual(settings["trustedWorkspaces"], [link, os.path.realpath(self.folder)])

    def test_unreadable_claude_config_is_left_alone(self):
        path = os.path.join(self.home, ".claude.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(ensure_trusted(self.session("claude"), self.folder), "unreadable .claude.json")
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "{not json")

    def test_every_setting_off_writes_nothing(self):
        for provider in ("claude", "antigravity", "codex"):
            session = self.session(provider, auto_trust_folder=False, auto_trust_hooks=False, codex_update_prompt=True)
            self.assertIsNone(ensure_trusted(session, self.folder, popen_factory=mock.Mock(side_effect=AssertionError)))
        self.assertEqual(os.listdir(self.home), [])

    def test_folder_setting_alone_governs_claude_and_antigravity(self):
        for provider in ("claude", "antigravity"):
            ensure_trusted(self.session(provider, auto_trust_folder=False), self.folder)
        self.assertEqual(os.listdir(self.home), [])
        ensure_trusted(self.session("claude", auto_trust_hooks=False), self.folder)
        self.assertTrue(_read(os.path.join(self.home, ".claude.json"))["projects"][claude_project_key(self.folder)]["hasTrustDialogAccepted"])

    def test_codex_settings_apply_independently(self):
        hooks = {"k": "sha256:a"}
        only_hooks = _FakeAppServer(hooks)
        _trust_codex(self.home, trust_paths(self.folder), {}, only_hooks, folder=False)
        # The first write is the update prompt alone; no folder is trusted.
        self.assertEqual(only_hooks.methods(), ["initialize", "config/batchWrite", "hooks/list", "config/batchWrite"])
        self.assertEqual(only_hooks.projects, {})
        only_folder = _FakeAppServer(hooks)
        _trust_codex(self.home, trust_paths(self.folder), {}, only_folder, hooks=False)
        self.assertEqual(only_folder.methods(), ["initialize", "config/batchWrite"])
        self.assertEqual(only_folder.state, {})
        with mock.patch("src.launch_trust._trust_codex", return_value=None) as trust:
            ensure_trusted(self.session("codex", auto_trust_hooks=False), self.folder)
        self.assertEqual(trust.call_args.kwargs, {"folder": True, "hooks": False, "update_prompt": False})

    def test_codex_update_prompt_follows_its_setting(self):
        config = os.path.join(self.home, "config.toml")
        trust_off = {"folder": False, "hooks": False}
        server = _FakeAppServer({})
        _trust_codex(self.home, trust_paths(self.folder), {}, server, **trust_off)
        self.assertEqual(server.config, {"check_for_update_on_startup": False})
        with open(config, "w", encoding="utf-8") as handle:
            handle.write("check_for_update_on_startup = false\n")
        # Already suppressed: no app-server at all.
        self.assertIsNone(_trust_codex(self.home, trust_paths(self.folder), {}, mock.Mock(side_effect=AssertionError), **trust_off))
        server = _FakeAppServer({})
        _trust_codex(self.home, trust_paths(self.folder), {}, server, update_prompt=True, **trust_off)
        try:
            import tomllib  # noqa: F401
        except ImportError:
            return
        self.assertEqual(server.config, {"check_for_update_on_startup": True})
        os.remove(config)
        # Codex prompts by default, so turning the prompt on writes nothing to a fresh config.
        self.assertIsNone(_trust_codex(self.home, trust_paths(self.folder), {}, mock.Mock(side_effect=AssertionError),
                                       update_prompt=True, **trust_off))

    def test_antigravity_trust_appends_and_keeps_settings(self):
        path = os.path.join(self.home, ".gemini", "antigravity-cli", "settings.json")
        status_line = {"type": "command", "command": "status"}
        _write(path, {"model": "Gemini", "statusLine": status_line, "trustedWorkspaces": ["/already"]})
        session = self.session("antigravity")

        self.assertIsNone(ensure_trusted(session, self.folder))
        expected = {"model": "Gemini", "statusLine": status_line,
                    "trustedWorkspaces": ["/already", *trust_paths(self.folder)]}
        self.assertEqual(_read(path), expected)
        with mock.patch("src.launch_trust._write_json") as write:
            ensure_trusted(session, self.folder)
        write.assert_not_called()
        self.assertFalse(os.path.exists(os.path.join(self.other_home, ".gemini")))

    def test_antigravity_unexpected_trust_list_is_left_alone(self):
        path = os.path.join(self.home, ".gemini", "antigravity-cli", "settings.json")
        _write(path, {"trustedWorkspaces": "/odd"})
        self.assertEqual(ensure_trusted(self.session("antigravity"), self.folder), "unreadable Antigravity settings.json")
        self.assertEqual(_read(path), {"trustedWorkspaces": "/odd"})

    def test_codex_trusts_the_folder_then_every_pending_hook(self):
        server = _FakeAppServer({
            "/home/hooks.json:pre_tool_use:0:0": "sha256:user",
            "plugin@market:hooks/hooks.json:stop:0:0": "sha256:definition/sha256:content",
        })
        self.assertIsNone(_trust_codex(self.home, trust_paths(self.folder), {"PATH": ""}, server))

        self.assertEqual(server.env["CODEX_HOME"], self.home)
        self.assertEqual(server.argv[1:], ["app-server", "--listen", "stdio://"])
        # The folder is written before the listing, so the project's own hooks show up.
        self.assertEqual(server.methods(), ["initialize", "config/batchWrite", "hooks/list", "config/batchWrite"])
        self.assertEqual(server.projects, {path: {"trust_level": "trusted"} for path in trust_paths(self.folder)})
        self.assertEqual(server.state, {
            "/home/hooks.json:pre_tool_use:0:0": {"trusted_hash": "sha256:user"},
            "plugin@market:hooks/hooks.json:stop:0:0": {"trusted_hash": "sha256:definition",
                                                        "trusted_content_hash": "sha256:content"},
        })
        upserts = [edit["mergeStrategy"] for request in server.requests if request["method"] == "config/batchWrite"
                   for edit in request["params"]["edits"]]
        self.assertEqual(upserts, ["upsert", "replace", "upsert"])
        self.assertEqual(server.config, {"check_for_update_on_startup": False})

    def test_codex_writes_nothing_once_everything_is_trusted(self):
        paths = trust_paths(self.folder)
        with open(os.path.join(self.home, "config.toml"), "w", encoding="utf-8") as handle:
            handle.write('model = "gpt"\ncheck_for_update_on_startup = false\n' + "".join(f'\n[projects.{json.dumps(p)}]\ntrust_level = "trusted"\n' for p in paths))
        server = _FakeAppServer({"k": "sha256:a"}, trusted_projects=paths)
        server.state = {"k": {"trusted_hash": "sha256:a"}}
        self.assertIsNone(_trust_codex(self.home, paths, {}, server))
        try:
            import tomllib  # noqa: F401
        except ImportError:
            # Without a TOML reader the folder trust is re-sent; Codex's upsert keeps it as is.
            self.assertEqual(server.methods(), ["initialize", "config/batchWrite", "hooks/list"])
        else:
            self.assertEqual(server.methods(), ["initialize", "hooks/list"])

    def test_codex_without_hook_listing_still_trusts_the_folder(self):
        server = _FakeAppServer({})
        answer = server.answer
        server.answer = lambda message: None if message["method"] == "hooks/list" else answer(message)
        self.assertIsNone(_trust_codex(self.home, trust_paths(self.folder), {}, server, timeout=0.2))
        self.assertEqual(server.methods(), ["initialize", "config/batchWrite", "hooks/list"])

    def test_codex_missing_cli_is_reported_not_raised(self):
        reason = _trust_codex(self.home, trust_paths(self.folder), {}, mock.Mock(side_effect=FileNotFoundError("codex")))
        self.assertIn("codex app-server failed", reason)

    def test_codex_dispatch_reaches_the_app_server(self):
        with mock.patch("src.launch_trust._trust_codex", return_value=None) as trust:
            ensure_trusted(self.session("codex"), self.folder, env={"EXTRA": "1"})
        home, paths, env, _ = trust.call_args.args
        self.assertEqual((home, paths, env["EXTRA"]), (self.home, trust_paths(self.folder), "1"))

    def test_ollama_has_nothing_to_trust(self):
        self.assertIsNone(ensure_trusted(self.session("ollama"), self.folder))
        self.assertEqual(os.listdir(self.home), [])


class AutoTrustSettingTests(CliTestBase):
    def test_set_and_unset_parse_both_settings(self):
        parsed = _parse_set_args(["work", "--auto-trust-folder", "off", "--auto-trust-hooks", "on", "--codex-update-prompt", "on"])
        self.assertEqual(parsed["settings"], {"auto_trust_folder": False, "auto_trust_hooks": True, "codex_update_prompt": True})
        self.assertEqual(_parse_unset_args(["work", "--auto-trust-folder", "--auto-trust-hooks", "--codex-update-prompt"])["keys"],
                         ["auto_trust_folder", "auto_trust_hooks", "codex_update_prompt"])

    def test_config_shows_both_settings_on_by_default(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")
        io = self.make_io()
        main(["config", "work"], {**io, "service": service})
        self.assertIn("Auto-trust folder", io["stdout"].getvalue())
        self.assertIn("Auto-trust hooks", io["stdout"].getvalue())
        self.assertRegex(io["stdout"].getvalue(), r"Codex update prompt\s+off")
        main(["set", "work", "--auto-trust-hooks", "off"], {**self.make_io(), "service": service})
        io = self.make_io()
        main(["config", "work", "--json"], {**io, "service": service})
        self.assertIs(json.loads(io["stdout"].getvalue())["session"]["launch"]["auto_trust_hooks"], False)

    def test_launch_records_trust_unless_turned_off(self):
        temp_dir = self.make_temp_dir()
        folder = os.path.realpath(self.make_temp_dir())
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main", "claude")
        harness = _AuthHarness()

        def launch():
            with mock.patch("src.commands.launch._run_interactive_provider_command",
                            return_value={"returncode": 0}), \
                    mock.patch("src.commands.launch._ensure_session_authentication"):
                self.assertEqual(main(["start", "main", "--dir", folder], {
                    **self.make_io(), "service": service, "env": {},
                    "spawn": harness.spawn, "spawn_sync": harness.spawn_sync,
                }), 0)
            path = os.path.join(service["get_session"]("main")["authHome"], ".claude.json")
            return _read(path).get("projects", {}) if os.path.exists(path) else {}

        main(["set", "main", "--auto-trust-folder", "off"], {**self.make_io(), "service": service})
        self.assertNotIn(claude_project_key(folder), launch())
        main(["unset", "main", "--auto-trust-folder"], {**self.make_io(), "service": service})
        self.assertTrue(launch()[claude_project_key(folder)]["hasTrustDialogAccepted"])


if __name__ == "__main__":
    unittest.main()
