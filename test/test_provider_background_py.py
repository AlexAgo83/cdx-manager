"""Tests for delegating detached runs to a provider's own background agents."""

import json
import tempfile
import unittest

from src.provider_background import (
    agent_terminal_status,
    find_agent,
    list_background_agents,
    parse_backgrounded_id,
    supports_native_background,
)

ON = {"CDX_EXPERIMENTAL_NATIVE_BG": "1"}


def _runner(responses):
    def run(argv, env=None):
        return responses.get(" ".join(argv))
    return run


class CapabilityDetectionTests(unittest.TestCase):
    def test_requires_both_starting_and_observing(self):
        both = _runner({
            "claude --help": "  --bg, --background  Start the session as a background agent",
            "claude agents --help": "  --json  Print active sessions as a JSON array",
        })
        self.assertTrue(supports_native_background("claude", env=ON, spawn_sync=both))

        # An agent cdx can start but never observe would leave runs stuck at
        # "running" forever, which is worse than not delegating at all.
        start_only = _runner({
            "claude --help": "  --bg  Start the session as a background agent",
            "claude agents --help": "  --cwd <path>  Filter by directory",
        })
        self.assertFalse(supports_native_background("claude", env=ON, spawn_sync=start_only))

    def test_codex_is_not_delegated_to_while_its_surface_is_experimental(self):
        anything = _runner({
            "codex --help": "--bg",
            "codex agents --help": "--json",
        })
        self.assertFalse(supports_native_background("codex", env=ON, spawn_sync=anything))

    def test_an_unreadable_cli_is_not_a_capability(self):
        self.assertFalse(supports_native_background("claude", env=ON, spawn_sync=_runner({})))


    def test_delegation_is_off_unless_explicitly_opted_in(self):
        """Live trial showed the provider assigns its own id under --bg, so cdx
        could not identify the agent it had just started, fell back, and ran the
        task twice. Off by default until that is understood."""
        capable = _runner({
            "claude --help": "  --bg  Start the session as a background agent",
            "claude agents --help": "  --json  Print active sessions as a JSON array",
        })

        self.assertFalse(supports_native_background("claude", env={}, spawn_sync=capable))
        self.assertTrue(supports_native_background("claude", env=ON, spawn_sync=capable))


class BackgroundedIdTests(unittest.TestCase):
    def test_reads_the_id_claude_prints_at_launch(self):
        # The provider assigns the id and ignores --session-id, so this line is
        # the only reliable way to name the agent just started.
        output = "backgrounded \u00b7 8a93f198\n  claude agents             list sessions\n"
        self.assertEqual(parse_backgrounded_id(output), "8a93f198")

    def test_returns_none_when_no_id_was_reported(self):
        for text in ("", None, "some unrelated output"):
            self.assertIsNone(parse_backgrounded_id(text))


class AgentListingTests(unittest.TestCase):
    def test_parses_the_agent_array(self):
        agents = [{"pid": 1, "sessionId": "abc", "status": "busy"}]
        runner = _runner({"claude agents --json --all": json.dumps(agents)})

        found = list_background_agents(spawn_sync=runner)

        self.assertEqual(found, agents)
        self.assertEqual(find_agent(found, "abc")["pid"], 1)
        self.assertEqual(find_agent([{"id": "8a93f198"}], "8a93f198")["id"], "8a93f198")
        self.assertIsNone(find_agent(found, "missing"))

    def test_any_failure_yields_an_empty_list_rather_than_raising(self):
        # This feeds a status refresh that must never take down the command
        # that asked for it.
        for payload in (None, "", "not json", "{}"):
            self.assertEqual(list_background_agents(spawn_sync=_runner(
                {"claude agents --json --all": payload}
            )), [])


class TerminalStatusTests(unittest.TestCase):
    def test_completion_is_read_from_state_not_status(self):
        """Observed by watching one agent from launch to finish.

        `status` alternates idle/busy - it describes activity, not outcome - so
        a waiting agent (`state: blocked`, `status: idle`) reads exactly like a
        finished one if you look at `status`. The first implementation did.
        """
        self.assertEqual(agent_terminal_status({"state": "done", "status": "idle"}), "succeeded")
        self.assertIsNone(agent_terminal_status({"state": "blocked", "status": "idle"}))
        self.assertIsNone(agent_terminal_status({"status": "completed"}))

    def test_non_success_terminal_states_map_to_failed(self):
        for state in ("failed", "cancelled", "error", "stopped"):
            self.assertEqual(agent_terminal_status({"state": state}), "failed")

    def test_an_agent_the_provider_no_longer_lists_is_never_called_a_success(self):
        # Its outcome was never observed, and success is the one answer that
        # must not be guessed.
        self.assertEqual(agent_terminal_status(None), "failed")


class BackgroundArgvTests(unittest.TestCase):
    def test_background_argv_never_carries_print_only_flags(self):
        """`--bg` does not pass `--print`, so print-only flags must not ride along.

        Regression: the first implementation reused the headless spec and
        stripped `--print`, which left `--output-format`, `--max-budget-usd` and
        `--fallback-model` on a command line that no longer had `--print`.
        """
        from src.commands.runs import _spawn_provider_background_run

        session = {
            "name": "s",
            "provider": "claude",
            "authHome": "/tmp/home",
            "conversation": {"id": "11111111-2222-3333-4444-555555555555", "provenance": "imposed"},
            "launch": {"budget": 5.0, "fallback_model": "haiku", "model": "sonnet"},
        }
        captured = {}

        def spawn(argv, **_kwargs):
            captured["argv"] = argv
            raise OSError("stop after capturing argv")

        _spawn_provider_background_run(
            session,
            "do it",
            {"transcript_path": tempfile.mktemp(suffix=".log")},
            {"spawn_detached": spawn},
            "/tmp/repo",
        )

        argv = captured["argv"]
        self.assertEqual(argv[:2], ["claude", "--bg"])
        for flag in ("--print", "--output-format", "--max-budget-usd", "--fallback-model"):
            self.assertNotIn(flag, argv, f"{flag} is print-only and must not reach a --bg launch")
        # The settings that do apply to a session still travel.
        self.assertIn("--session-id", argv)
        self.assertIn("--model", argv)
