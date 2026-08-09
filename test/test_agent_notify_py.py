import io
import json
import os
import tempfile
import unittest
from unittest import mock

from src import agent_notify


class HookTargetTests(unittest.TestCase):
    def _ctx(self, stdin_text=None, env=None, calls=None):
        return {
            "prompt_stdin": io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
            "stdin_is_tty": False,
            "env": env or {},
            "cwd": "/repos/crh-manager",
            "spawn_sync": (lambda argv, **kwargs: calls.append(argv)) if calls is not None else None,
        }

    def test_reads_claude_style_payload_from_stdin(self):
        payload = json.dumps({"hook_event_name": "Stop", "cwd": "/repos/logics-manager"})
        title, message = agent_notify.compose_notification(
            agent_notify.read_hook_payload([], payload),
            {agent_notify.SESSION_ENV: "work1"},
        )
        self.assertEqual(title, "✓ work1")
        self.assertIn("logics-manager", message)
        self.assertIn("finished", message)

    def test_reads_codex_legacy_payload_from_argv(self):
        payload = json.dumps({"type": "agent-turn-complete", "cwd": "/repos/cdx-manager"})
        title, message = agent_notify.compose_notification(
            agent_notify.read_hook_payload([payload]),
            {agent_notify.SESSION_ENV: "codex-a"},
        )
        self.assertEqual(title, "✓ codex-a")
        self.assertIn("cdx-manager", message)

    def test_waiting_and_finished_read_differently(self):
        env = {agent_notify.SESSION_ENV: "perso"}
        _, waiting = agent_notify.compose_notification({"hook_event_name": "Notification", "cwd": "/r/a"}, env)
        _, done = agent_notify.compose_notification({"hook_event_name": "Stop", "cwd": "/r/a"}, env)
        self.assertNotEqual(waiting, done)
        self.assertIn("waiting", waiting)

    def test_parallel_sessions_are_distinguishable(self):
        one = agent_notify.compose_notification({"cwd": "/repos/alpha"}, {agent_notify.SESSION_ENV: "work1"})
        two = agent_notify.compose_notification({"cwd": "/repos/beta"}, {agent_notify.SESSION_ENV: "perso"})
        self.assertNotEqual(one[0], two[0])
        self.assertNotEqual(one[1], two[1])

    def test_headless_runs_stay_silent(self):
        env = {agent_notify.SESSION_ENV: "work1", agent_notify.ENABLED_ENV: "0"}
        self.assertIsNone(agent_notify.compose_notification({"cwd": "/r/a"}, env))

    def test_malformed_payload_never_fails_the_caller(self):
        for bad in ("", "not json", "[1,2,3]", "null"):
            self.assertEqual(agent_notify.read_hook_payload([], bad), {})
        calls = []
        self.assertEqual(agent_notify.handle_notify([], self._ctx("not json", {}, calls)), 0)
        self.assertEqual(calls, [])

    def test_handle_notify_swallows_a_broken_notifier(self):
        ctx = self._ctx(json.dumps({"cwd": "/r/a"}), {agent_notify.SESSION_ENV: "work1"})
        ctx["spawn_sync"] = mock.Mock(side_effect=OSError("boom"))
        self.assertEqual(agent_notify.handle_notify([], ctx), 0)

    def test_hook_command_resolves_rather_than_using_the_bare_name(self):
        self.assertEqual(agent_notify.resolve_hook_command({"CDX_BIN": "C:\\cdx.cmd"}), "C:\\cdx.cmd")


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = {"CDX_BIN": "/usr/local/bin/cdx", "PATH": ""}

    def _read(self, provider):
        with open(agent_notify.hook_config_path(self.home, provider), encoding="utf-8") as handle:
            return json.load(handle)

    def _provision(self, provider, enabled=True, channel="osascript"):
        with mock.patch.object(agent_notify, "notification_channel", return_value=channel):
            return agent_notify.provision(self.home, provider, enabled, self.env)

    def test_codex_config_sits_at_the_codex_home_root(self):
        self.assertTrue(self._provision("codex"))
        self.assertTrue(os.path.exists(os.path.join(self.home, "hooks.json")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".codex", "config.toml")))

    def test_installs_for_claude_under_its_own_home(self):
        self.assertTrue(self._provision("claude"))
        hooks = self._read("claude")["hooks"]
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], "/usr/local/bin/cdx notify")
        self.assertIn("Notification", hooks)

    def test_second_launch_changes_nothing(self):
        self.assertTrue(self._provision("claude"))
        first = self._read("claude")
        self.assertFalse(self._provision("claude"))
        self.assertEqual(first, self._read("claude"))

    def test_preserves_unrelated_settings_and_user_hooks(self):
        path = agent_notify.hook_config_path(self.home, "claude")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mine = {"type": "command", "command": "echo mine"}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"theme": "dark", "hooks": {"Stop": [{"hooks": [mine]}]}}, handle)

        self._provision("claude")
        document = self._read("claude")
        self.assertEqual(document["theme"], "dark")
        self.assertIn({"hooks": [mine]}, document["hooks"]["Stop"])

        self._provision("claude", enabled=False)
        document = self._read("claude")
        self.assertEqual(document["hooks"]["Stop"], [{"hooks": [mine]}])

    def test_turning_off_removes_only_our_entries(self):
        self._provision("claude")
        self.assertFalse(self._provision("claude", enabled=False))
        self.assertEqual(self._read("claude")["hooks"], {})

    def test_no_hooks_installed_without_a_delivery_channel(self):
        self.assertFalse(self._provision("claude", channel=None))
        self.assertFalse(os.path.exists(agent_notify.hook_config_path(self.home, "claude")))
        # A host that gains a channel later is provisioned on its next launch.
        self.assertTrue(self._provision("claude", channel="notify-send"))

    def test_unparseable_config_is_left_untouched(self):
        path = agent_notify.hook_config_path(self.home, "claude")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertFalse(self._provision("claude"))
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "{ not json")

    def test_notifications_are_on_unless_turned_off(self):
        self.assertTrue(agent_notify.notifications_enabled({"name": "a"}))
        self.assertTrue(agent_notify.notifications_enabled({"name": "a", "launch": {}}))
        self.assertFalse(agent_notify.notifications_enabled({"name": "a", "launch": {"notify": False}}))

    def test_launch_env_carries_the_session_and_the_suppression(self):
        session = {"name": "work1"}
        self.assertEqual(agent_notify.launch_notify_env(session, True), {agent_notify.SESSION_ENV: "work1"})
        self.assertEqual(
            agent_notify.launch_notify_env(session, False),
            {agent_notify.SESSION_ENV: "work1", agent_notify.ENABLED_ENV: "0"},
        )


if __name__ == "__main__":
    unittest.main()
