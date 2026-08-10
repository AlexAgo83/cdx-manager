import os
import unittest

from src.config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA
from src.errors import CdxError
from src.provider_runtime import (
    TERMINAL_TITLE_SEPARATOR,
    _claude_cli_model,
    _codex_fast_config_args,
    _launch_config_args,
    _launch_power,
    _legacy_fast_low_effort,
    _normalize_reasoning_effort,
    _redact_sensitive_args,
    _sanitize_terminal_title_component,
    _start_terminal_title,
    _TerminalTitleKeeper,
    format_terminal_title,
)


class NormalizeReasoningEffortTests(unittest.TestCase):
    def test_empty_value_rejected(self):
        with self.assertRaises(CdxError):
            _normalize_reasoning_effort(reasoning_effort="")
        with self.assertRaises(CdxError):
            _normalize_reasoning_effort(power="")

    def test_unsupported_values_rejected(self):
        with self.assertRaises(CdxError):
            _normalize_reasoning_effort(reasoning_effort="turbo")
        with self.assertRaises(CdxError):
            _normalize_reasoning_effort(power="turbo")

    def test_mismatch_rejected(self):
        with self.assertRaises(CdxError):
            _normalize_reasoning_effort(reasoning_effort="high", power="low")

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_reasoning_effort(), {})

    def test_resolved_mirrors_to_both_keys(self):
        self.assertEqual(
            _normalize_reasoning_effort(reasoning_effort="HIGH"),
            {"reasoning_effort": "high", "power": "high"},
        )
        # matching effort+power is allowed
        self.assertEqual(
            _normalize_reasoning_effort(reasoning_effort="low", power="low"),
            {"reasoning_effort": "low", "power": "low"},
        )


class ClaudeCliModelTests(unittest.TestCase):
    def test_empty_passthrough(self):
        self.assertIsNone(_claude_cli_model(None))
        self.assertEqual(_claude_cli_model(""), "")

    def test_named_aliases(self):
        self.assertEqual(_claude_cli_model("claude-sonnet"), "sonnet")
        self.assertEqual(_claude_cli_model("opus-latest"), "opus")

    def test_marketing_names(self):
        self.assertEqual(_claude_cli_model("claude-sonnet-4-5"), "claude-sonnet-4-5")
        self.assertEqual(_claude_cli_model("sonnet-4"), "sonnet")  # no minor -> family only

    def test_dated_names_strip_date(self):
        self.assertEqual(_claude_cli_model("claude-sonnet-4-5-20250101"), "claude-sonnet-4-5")

    def test_unknown_passthrough_preserves_original(self):
        self.assertEqual(_claude_cli_model("gpt-4o"), "gpt-4o")


class LaunchPowerTests(unittest.TestCase):
    def test_explicit_power_wins(self):
        self.assertEqual(_launch_power({"launch": {"power": "high"}}), "high")
        self.assertEqual(_launch_power({"launch": {"reasoningEffort": "medium"}}), "medium")

    def test_legacy_fast_maps_to_low(self):
        self.assertTrue(_legacy_fast_low_effort({"fast": True}))
        self.assertFalse(_legacy_fast_low_effort({"fast": True, "fastMode": "service_tier"}))
        self.assertEqual(_launch_power({"launch": {"fast": True}}), "low")

    def test_no_settings_is_none(self):
        self.assertIsNone(_launch_power({"launch": {}}))

    def test_codex_fast_config_args(self):
        self.assertIn('service_tier="fast"', _codex_fast_config_args({"fast": True, "fastMode": "service_tier"}))
        self.assertIn('service_tier="flex"', _codex_fast_config_args({}))


class LaunchConfigArgsTests(unittest.TestCase):
    def test_claude_effort_and_permission(self):
        args = _launch_config_args({
            "provider": PROVIDER_CLAUDE,
            "launch": {"power": "high", "permission": "review"},
        })
        self.assertEqual(args, ["--effort", "high", "--permission-mode", "plan"])

    def test_codex_power_fast_and_permission(self):
        args = _launch_config_args({
            "provider": PROVIDER_CODEX,
            "launch": {"power": "medium", "permission": "full", "fast": True, "fastMode": "service_tier"},
        })
        self.assertIn('model_reasoning_effort="medium"', args)
        self.assertIn('service_tier="fast"', args)
        # codex "full" permission maps to danger-full-access sandbox flags
        self.assertIn("danger-full-access", args)

    def test_antigravity_permissions(self):
        self.assertEqual(
            _launch_config_args({"provider": PROVIDER_ANTIGRAVITY, "launch": {"permission": "review"}}),
            ["--sandbox"],
        )
        self.assertEqual(
            _launch_config_args({"provider": PROVIDER_ANTIGRAVITY, "launch": {"permission": "full"}}),
            ["--dangerously-skip-permissions"],
        )

    def test_ollama_permission_maps_to_nothing(self):
        for permission in ("full", "review", "safe", None):
            self.assertEqual(
                _launch_config_args(
                    {"provider": PROVIDER_OLLAMA, "launch": {"permission": permission}}
                ),
                [],
            )


class RedactSensitiveArgsTests(unittest.TestCase):
    def test_no_sensitive_returns_args_unchanged(self):
        spec = {"args": ["--prompt", "hello"]}
        self.assertEqual(_redact_sensitive_args(spec), ["--prompt", "hello"])

    def test_sensitive_values_are_redacted(self):
        spec = {"args": ["--prompt", "secret-text"], "sensitive_args": ["secret-text"]}
        out = _redact_sensitive_args(spec)
        self.assertNotIn("secret-text", out)
        self.assertIn("--prompt", out)


class TerminateChildTreeTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "getpgid"), "process groups unavailable")
    def test_kills_grandchildren_in_the_process_group(self):
        import subprocess
        import time

        from src.provider_runtime import _terminate_child_tree

        child = subprocess.Popen(["sh", "-c", "sleep 60 & wait"], start_new_session=True)
        pgid = os.getpgid(child.pid)
        _terminate_child_tree(child)
        for _ in range(50):
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.killpg(pgid, 9)
            self.fail("process group still has live members after termination")


class FakeTitleStream:
    def __init__(self, tty=True):
        self.tty = tty
        self.writes = []
        self.flushes = 0

    def isatty(self):
        return self.tty

    def write(self, value):
        self.writes.append(value)
        return len(value)

    def flush(self):
        self.flushes += 1


class TerminalTitleFormatTests(unittest.TestCase):
    def test_format_is_session_then_folder(self):
        self.assertEqual(
            format_terminal_title("main", "/home/dev/cdx-manager"),
            f"main{TERMINAL_TITLE_SEPARATOR}cdx-manager",
        )

    def test_folder_is_basename_of_effective_cwd(self):
        self.assertEqual(
            format_terminal_title("main", os.getcwd()),
            f"main{TERMINAL_TITLE_SEPARATOR}{os.path.basename(os.getcwd())}",
        )
        self.assertEqual(format_terminal_title("main"), format_terminal_title("main", os.getcwd()))

    def test_root_directory_keeps_the_path_as_folder(self):
        root = os.path.abspath("/")
        self.assertEqual(format_terminal_title("main", root), f"main{TERMINAL_TITLE_SEPARATOR}{root}")

    def test_missing_part_does_not_leave_an_empty_half(self):
        self.assertEqual(format_terminal_title("", "/home/dev/repo"), "repo")

    def test_control_characters_are_stripped(self):
        title = format_terminal_title("ma\x1b]0;evil\x07in\nname", "/home/dev/re\x9cpo")
        self.assertEqual(title, f"ma]0;evilinname{TERMINAL_TITLE_SEPARATOR}repo")
        for forbidden in ("\x1b", "\x07", "\n", "\x9c", "\x00"):
            self.assertNotIn(forbidden, title)

    def test_sanitizer_handles_missing_values(self):
        self.assertEqual(_sanitize_terminal_title_component(None), "")
        self.assertEqual(_sanitize_terminal_title_component("  spaced  "), "spaced")


class TerminalTitleKeeperTests(unittest.TestCase):
    def test_start_writes_the_osc_sequence_once(self):
        stream = FakeTitleStream()
        keeper = _TerminalTitleKeeper("main — repo", stream, interval=0).start()
        try:
            self.assertEqual(stream.writes, ["\033]0;main — repo\007"])
            self.assertEqual(stream.flushes, 1)
        finally:
            keeper.stop()

    def test_title_is_reasserted_while_the_provider_runs(self):
        import time

        stream = FakeTitleStream()
        keeper = _TerminalTitleKeeper("main — repo", stream, interval=0.01).start()
        try:
            deadline = time.time() + 2
            while len(stream.writes) < 3 and time.time() < deadline:
                time.sleep(0.01)
            self.assertGreaterEqual(len(stream.writes), 3)
        finally:
            keeper.stop()
        written = len(stream.writes)
        time.sleep(0.05)
        self.assertEqual(len(stream.writes), written)

    def test_unwritable_stream_never_raises(self):
        class BrokenStream(FakeTitleStream):
            def write(self, value):
                raise ValueError("closed")

        keeper = _TerminalTitleKeeper("main — repo", BrokenStream(), interval=0.01).start()
        keeper.stop()


class StartTerminalTitleTests(unittest.TestCase):
    def session(self, provider=PROVIDER_CLAUDE):
        return {"name": "main", "provider": provider}

    def test_launch_and_resume_on_a_tty_hold_the_title(self):
        for action in ("launch", "resume"):
            stream = FakeTitleStream()
            keeper = _start_terminal_title(self.session(), action, cwd="/home/dev/repo", stream=stream)
            self.assertIsNotNone(keeper)
            keeper.stop()
            self.assertEqual(stream.writes, [f"\033]0;main{TERMINAL_TITLE_SEPARATOR}repo\007"])

    def test_every_supported_provider_uses_the_same_runtime_path(self):
        for provider in (PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_ANTIGRAVITY):
            stream = FakeTitleStream()
            keeper = _start_terminal_title(
                self.session(provider), "launch", cwd="/home/dev/repo", stream=stream
            )
            self.assertIsNotNone(keeper, provider)
            keeper.stop()
            self.assertEqual(stream.writes, [f"\033]0;main{TERMINAL_TITLE_SEPARATOR}repo\007"])

    def test_non_tty_stream_writes_nothing(self):
        stream = FakeTitleStream(tty=False)
        self.assertIsNone(_start_terminal_title(self.session(), "launch", cwd="/home/dev/repo", stream=stream))
        self.assertEqual(stream.writes, [])

    def test_stream_without_isatty_writes_nothing(self):
        class Captured:
            def __init__(self):
                self.writes = []

            def write(self, value):
                self.writes.append(value)

        stream = Captured()
        self.assertIsNone(_start_terminal_title(self.session(), "launch", stream=stream))
        self.assertEqual(stream.writes, [])

    def test_disabled_json_run_writes_nothing(self):
        stream = FakeTitleStream()
        self.assertIsNone(
            _start_terminal_title(self.session(), "launch", stream=stream, enabled=False)
        )
        self.assertEqual(stream.writes, [])

    def test_auth_actions_and_ollama_are_untouched(self):
        stream = FakeTitleStream()
        self.assertIsNone(_start_terminal_title(self.session(), "login", stream=stream))
        self.assertIsNone(_start_terminal_title(self.session(), "setup-token", stream=stream))
        self.assertIsNone(
            _start_terminal_title(self.session(PROVIDER_OLLAMA), "launch", stream=stream)
        )
        self.assertEqual(stream.writes, [])


if __name__ == "__main__":
    unittest.main()
