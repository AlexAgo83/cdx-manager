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

    def test_codex_network_override_keeps_the_workspace_sandbox(self):
        captured = {}
        spec = {"command": "codex", "args": ["--", "A prompt"], "options": {"env": {"PATH": "/usr/bin"}}}

        def confine(command, tree, **kw):
            captured.update(command=command, **kw)
            return ["bwrap", "confined"], {"HOME": "/home/agent"}

        class Reached(Exception):
            pass

        session = {"provider": "codex", "authHome": "/profile",
                   "launch": {"permission": "auto", "network_access": True, "isolate_workspace": True}}
        with TemporaryDirectory() as tree, \
                mock.patch.object(provider_runtime, "_build_headless_launch_spec", lambda *a, **kw: spec), \
                mock.patch.object(workspace_sandbox, "sandbox_command", confine), \
                mock.patch.object(provider_runtime, "_headless_artifact_paths", mock.Mock(side_effect=Reached)):
            with self.assertRaises(Reached):
                provider_runtime._run_headless_provider_command(session, cwd=str(Path(tree)))
        self.assertTrue(captured["network"])
        self.assertIn("sandbox_workspace_write.network_access=true", captured["command"])
        self.assertNotIn("danger-full-access", captured["command"])
        self.assertEqual(spec["command"], "bwrap")

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

    def test_missing_pasta_fails_closed(self):
        with TemporaryDirectory() as tree, mock.patch.object(
                workspace_sandbox.shutil, "which",
                side_effect=lambda name, path=None: None if name == "pasta" else "/usr/bin/" + name):
            with self.assertRaises(RuntimeError):
                workspace_sandbox.sandbox_command(["true"], Path(tree), network=True, source={"PATH": "/usr/bin"})
