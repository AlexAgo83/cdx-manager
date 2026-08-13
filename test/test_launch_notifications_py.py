import unittest

from cli_test_support import CliTestBase

from src.commands.launch import _notification_provisioning_enabled
from src.tray_alerts import alerts_enabled
from src.tray_defaults import alerts_default


class LaunchNotificationConsentTest(CliTestBase):
    def _ctx(self, base_dir, answer="n", tty=True):
        return {
            "service": {"base_dir": base_dir},
            "stdin_is_tty": tty,
            "options": {"input": lambda _prompt: answer},
        }

    def test_declining_leaves_hook_consent_absent(self):
        base = self.make_temp_dir()
        self.assertFalse(_notification_provisioning_enabled({"provider": "codex", "launch": {}}, self._ctx(base), False))
        self.assertFalse(alerts_default(base))

    def test_accepting_persists_consent_and_starts_muted(self):
        base = self.make_temp_dir()
        self.assertTrue(_notification_provisioning_enabled({"provider": "claude", "launch": {}}, self._ctx(base, "yes"), False))
        self.assertTrue(alerts_default(base))
        self.assertFalse(alerts_enabled(base))

    def test_later_profile_uses_consent_without_another_prompt(self):
        base = self.make_temp_dir()
        self.assertTrue(_notification_provisioning_enabled({"provider": "codex", "launch": {}}, self._ctx(base, "yes"), False))
        self.assertTrue(_notification_provisioning_enabled({"provider": "claude", "launch": {}}, self._ctx(base, "must-not-be-read"), False))

    def test_non_interactive_launch_never_asks(self):
        base = self.make_temp_dir()
        self.assertFalse(_notification_provisioning_enabled({"provider": "codex", "launch": {}}, self._ctx(base, tty=False), False))


if __name__ == "__main__":
    unittest.main()
