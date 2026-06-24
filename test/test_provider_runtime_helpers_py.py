import unittest

from src.config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA
from src.errors import CdxError
from src.provider_runtime import (
    _claude_cli_model,
    _codex_fast_config_args,
    _launch_config_args,
    _launch_power,
    _legacy_fast_low_effort,
    _normalize_reasoning_effort,
    _redact_sensitive_args,
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

    def test_ollama_full_permission(self):
        self.assertEqual(
            _launch_config_args({"provider": PROVIDER_OLLAMA, "launch": {"permission": "full"}}),
            ["--experimental-yolo"],
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


if __name__ == "__main__":
    unittest.main()
