"""`cdx mcp serve`: tool argv building, validation and the stdio round trip."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

from src import mcp_server as server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _call(name, arguments, project_root="/work"):
    seen = {}

    def runner(args, input_text=None, timeout=None):
        seen.update(args=args, input=input_text, timeout=timeout)
        return {"ok": True}

    server.call_tool(name, arguments, project_root, runner)
    return seen


class McpServerTest(unittest.TestCase):
    def test_tools_are_read_and_run_only(self):
        names = {tool["name"] for tool in server.tool_definitions()}
        self.assertEqual(len(names), 14)
        self.assertIn("cdx_run_background", names)
        for excluded in ("rmv", "clean", "reset", "login", "logout", "set", "update", "export", "import"):
            self.assertNotIn(f"cdx_{excluded}", names)

    def test_run_resolves_the_project_and_sends_the_prompt_on_stdin(self):
        seen = _call("cdx_run_background", {"project": "app", "prompt": "do it; rm -rf /", "session": "alpha", "power": "high"})
        self.assertEqual(seen["args"], ["run", "alpha", "--cwd", os.path.join("/work", "app"), "--prompt-file", "-",
                                        "--power", "high", "--permission", "full", "--detach", "--json"])
        self.assertEqual(seen["input"], "do it; rm -rf /")

    def test_run_rejects_bad_targets(self):
        for arguments in ({"project": "..", "prompt": "x"}, {"project": "a/b", "prompt": "x"},
                          {"project": "app", "prompt": "x", "session": "alpha", "provider": "codex"},
                          {"project": "app", "prompt": "x"},
                          {"project": "app", "prompt": "x", "permission": "root"},
                          {"project": "app", "prompt": "x", "timeout_seconds": 0}):
            with self.assertRaises(server.ToolError, msg=arguments):
                _call("cdx_run", arguments)
        with self.assertRaisesRegex(server.ToolError, "project root"):
            _call("cdx_run", {"project": "app", "prompt": "x", "session": "alpha"}, project_root=None)

    def test_provider_mode_names_no_session(self):
        seen = _call("cdx_run", {"project": "app", "prompt": "x", "provider": "claude"})
        self.assertEqual(seen["args"][:6], ["run", "--cwd", os.path.join("/work", "app"), "--prompt-file", "-", "--provider"])

    def test_read_tools_build_their_commands(self):
        self.assertEqual(_call("cdx_configs", {})["args"], ["configs", "--json"])
        self.assertEqual(_call("cdx_configs", {"name": "alpha"})["args"], ["config", "alpha", "--json"])
        self.assertEqual(_call("cdx_run_tail", {"run_id": "r1"})["args"], ["run-tail", "r1", "--lines", "50", "--json"])
        self.assertEqual(_call("cdx_stats", {"since": "7d"})["args"], ["stats", "--since", "7d", "--json"])
        self.assertEqual(_call("cdx_disk", {"profiles": True, "candidates": True})["args"],
                         ["disk", "profiles", "--candidates", "--json"])
        with self.assertRaisesRegex(server.ToolError, "unsupported"):
            _call("cdx_last", {"extra": 1})

    def test_stdio_round_trip_runs_this_install(self):
        home = tempfile.mkdtemp()
        env = {**os.environ, "CDX_HOME": home, "HOME": home, "PYTHONPATH": ROOT}
        lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                 {"jsonrpc": "2.0", "method": "notifications/initialized"},
                 {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                 {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "cdx_configs", "arguments": {}}},
                 {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "cdx_run", "arguments": {"project": "x", "prompt": "y", "session": "alpha"}}}]
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "cdx"), "mcp", "serve"],
                              input="".join(json.dumps(line) + "\n" for line in lines),
                              capture_output=True, text=True, timeout=60, env=env, cwd=home)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([reply["id"] for reply in replies], [1, 2, 3, 4])
        self.assertIn("tools", replies[0]["result"]["capabilities"])
        self.assertEqual(len(replies[1]["result"]["tools"]), 14)
        self.assertFalse(replies[2]["result"]["isError"], replies[2])
        self.assertTrue(replies[3]["result"]["isError"])
        self.assertIn("project root", replies[3]["result"]["content"][0]["text"])

