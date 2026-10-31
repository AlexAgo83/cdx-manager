import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from src import provider_runtime, workspace_sandbox
from src.cli_args import _parse_run_args, cdx_schema
from src.commands.runs import _detached_child_argv
from src.errors import CdxError


class WorkspaceNetworkArgsTests(unittest.TestCase):
    def test_flags_survive_detached_reexec_and_schema_advertises_them(self):
        parsed = _parse_run_args(["work1", "--cwd", "/checkout", "--prompt", "Fix it", "--permission",
                                  "workspace-write", "--network-access", "--isolate-workspace",
                                  "--failover", "--detach", "--json"])
        self.assertTrue(parsed["network_access"])
        self.assertTrue(parsed["isolate_workspace"])
        argv = _detached_child_argv(parsed, "/prompt.txt", "work1", "/checkout")
        for flag in ("--network-access", "--isolate-workspace", "--failover"):
            self.assertIn(flag, argv)
        self.assertEqual(cdx_schema()["capabilities"], {"workspace_isolation": 1, "workspace_network": 1})


class WorkspaceSandboxTests(unittest.TestCase):
    def test_clean_env_drops_operator_credentials(self):
        env = workspace_sandbox.clean_env({"PATH": "/usr/bin", "GH_TOKEN": "fake-token-value",
                                           "GITHUB_TOKEN": "fake-token-value", "HOME": "/home/operator"})
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(env["HOME"], "/home/agent")
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], "")
        self.assertEqual(env["PLAYWRIGHT_SKIP_BROWSER_GC"], "1")
        self.assertEqual(workspace_sandbox.clean_env({"PLAYWRIGHT_SKIP_BROWSER_GC": "0"})["PLAYWRIGHT_SKIP_BROWSER_GC"], "1")

    def _run_isolated_codex(self, permission, network):
        captured = {}
        args = ["exec", "-s", "read-only" if permission == "review" else "workspace-write", "--", "A prompt"]
        spec = {"command": "codex", "args": args, "options": {"env": {"PATH": "/usr/bin"}}}

        def confine(command, tree, **kw):
            captured.update(command=command, **kw)
            return ["bwrap", "confined"], {"HOME": "/home/agent"}

        class Reached(Exception):
            pass

        session = {"provider": "codex", "authHome": "/profile",
                   "launch": {"permission": permission, "network_access": network, "isolate_workspace": True}}
        with TemporaryDirectory() as tree, \
                mock.patch.object(provider_runtime, "_build_headless_launch_spec", lambda *a, **kw: spec), \
                mock.patch.object(workspace_sandbox, "sandbox_command", confine), \
                mock.patch.object(provider_runtime, "_headless_artifact_paths", mock.Mock(side_effect=Reached)):
            with self.assertRaises(Reached):
                provider_runtime._run_headless_provider_command(session, cwd=str(Path(tree)))
        self.assertEqual(spec["command"], "bwrap")
        return captured

    def test_isolated_codex_drops_its_nested_sandbox(self):
        captured = self._run_isolated_codex("auto", network=True)
        command = captured["command"]
        self.assertTrue(captured["network"])
        self.assertTrue(captured["writable"])
        self.assertNotIn("-s", command)
        self.assertNotIn("sandbox_workspace_write.network_access=true", command)
        self.assertLess(command.index("--dangerously-bypass-approvals-and-sandbox"), command.index("--"))

    def test_isolated_codex_review_stays_read_only_outside(self):
        captured = self._run_isolated_codex("review", network=False)
        self.assertFalse(captured["writable"])
        self.assertNotIn("-s", captured["command"])
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", captured["command"])

    def test_unsupported_provider_fails_closed(self):
        with self.assertRaises(RuntimeError):
            workspace_sandbox.sandbox_command(["true"], Path("/nonexistent-tree"), network=True,
                                              source={"PATH": "/usr/bin"}, provider="ollama")


class NetworkOverrideProviderTests(unittest.TestCase):
    def test_network_override_refuses_other_providers(self):
        spec = {"command": "ollama", "args": [], "options": {"env": {}}}
        session = {"provider": "ollama", "launch": {"network_access": True}}
        with mock.patch.object(provider_runtime, "_build_headless_launch_spec", lambda *a, **kw: spec):
            with self.assertRaises(CdxError):
                provider_runtime._run_headless_provider_command(session, cwd="/tmp")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(sys.platform.startswith("linux"), "bubblewrap isolation is Linux-only")
class IsolatedEgressTests(unittest.TestCase):
    def test_online_runs_use_pasta_and_never_share_the_host_network(self):
        with TemporaryDirectory() as tree, mock.patch.object(workspace_sandbox.shutil, "which",
                                                             side_effect=lambda name, path=None: "/usr/bin/" + name):
            args, _ = workspace_sandbox.sandbox_command(["true"], Path(tree), network=True,
                                                        source={"PATH": "/usr/bin"})
        self.assertNotIn("--share-net", args)
        self.assertEqual(args[0], "/usr/bin/pasta")
        for flag in ("--no-map-gw", "-T", "-U"):
            self.assertIn(flag, args)

    def test_codex_observation_mount_exposes_only_fresh_attempt_sessions(self):
        with TemporaryDirectory() as tree, TemporaryDirectory() as observation, mock.patch.object(
                workspace_sandbox.shutil, "which", side_effect=lambda name, path=None: "/usr/bin/" + name):
            args, env = workspace_sandbox.sandbox_command(
                ["true"], Path(tree), network=False, provider="codex", auth_home="/private/profile",
                observation_home=observation, source={"PATH": "/usr/bin"})
        self.assertEqual(env["CODEX_HOME"], "/home/agent/.codex")
        self.assertIn("--cap-drop", args)
        self.assertNotIn("--share-net", args)
        self.assertNotIn("/private/profile", args)
        self.assertIn("/private/profile/auth.json", args)
        mount = args.index(observation)
        self.assertEqual(args[mount - 1:mount + 2], ["--bind", observation, "/home/agent/.codex/sessions"])

    def test_missing_pasta_fails_closed(self):
        with TemporaryDirectory() as tree, mock.patch.object(
                workspace_sandbox.shutil, "which",
                side_effect=lambda name, path=None: None if name == "pasta" else "/usr/bin/" + name):
            with self.assertRaises(RuntimeError):
                workspace_sandbox.sandbox_command(["true"], Path(tree), network=True, source={"PATH": "/usr/bin"})
