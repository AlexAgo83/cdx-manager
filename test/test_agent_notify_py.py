import io
import json
import os
import tempfile
import unittest
from unittest import mock

from src import agent_notify


class HookTargetTests(unittest.TestCase):
    def _ctx(self, stdin_text=None, env=None, calls=None):
        # The spawn double is never optional. `handle_notify` falls back to the
        # real desktop notifier when no tray is listening, and a test that left
        # spawn_sync unset raised an actual notification on the machine running
        # the suite — once per run, naming a session out of a fixture.
        calls = [] if calls is None else calls
        return {
            "prompt_stdin": io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
            "stdin_is_tty": False,
            "env": env or {},
            "cwd": "/repos/crh-manager",
            "spawn_sync": lambda argv, **kwargs: calls.append(argv),
        }

    def test_reads_claude_style_payload_from_stdin(self):
        payload = json.dumps({"hook_event_name": "Stop", "cwd": "/repos/logics-manager"})
        title, message = agent_notify.compose_notification(
            agent_notify.read_hook_payload([], payload),
            {agent_notify.SESSION_ENV: "work1"},
        )
        self.assertEqual(title, "✓ work1")
        self.assertIn("logics-manager", message)
        self.assertIn("turn complete", message)

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
        self.assertIn("needs your attention", waiting)

    def test_stop_preview_is_opt_in_and_sanitized(self):
        payload = {"hook_event_name": "Stop", "cwd": "/r/a", "last_assistant_message": "Done\nwith\x00 control"}
        env = {agent_notify.SESSION_ENV: "work1", agent_notify.PREVIEW_ENV: "1"}
        self.assertIn("Done with control", agent_notify.compose_notification(payload, env)[1])
        self.assertNotIn("Done with control", agent_notify.compose_notification(payload, {agent_notify.SESSION_ENV: "work1"})[1])

    def test_preview_is_bounded_and_attention_never_includes_it(self):
        text = "x" * 500
        env = {agent_notify.SESSION_ENV: "work1", agent_notify.PREVIEW_ENV: "1"}
        _, completed = agent_notify.compose_notification({"hook_event_name": "Stop", "last_assistant_message": text}, env)
        _, attention = agent_notify.compose_notification({"hook_event_name": "PermissionRequest", "tool_name": "Bash", "last_assistant_message": text}, env)
        self.assertTrue(completed.endswith("…"))
        self.assertLessEqual(len(completed.rsplit(" — ", 1)[1]), agent_notify._PREVIEW_LIMIT)
        self.assertIn("Bash", attention)
        self.assertNotIn(text[:20], attention)

    def test_a_permission_prompt_notification_is_dropped_as_a_duplicate(self):
        # PermissionRequest reports the same tool call immediately and by name.
        # Subscribing to both once meant two alerts for one request.
        env = {agent_notify.SESSION_ENV: "work1"}
        duplicate = agent_notify.compose_notification(
            {"hook_event_name": "Notification", "notification_type": "permission_prompt", "cwd": "/r/a"},
            env,
        )
        self.assertIsNone(duplicate)

    def test_the_waiting_notifications_nothing_else_reports_survive(self):
        env = {agent_notify.SESSION_ENV: "work1"}
        for kind in ("idle_prompt", "agent_needs_input"):
            _, message = agent_notify.compose_notification(
                {"hook_event_name": "Notification", "notification_type": kind, "cwd": "/r/a"},
                env,
            )
            self.assertIn("needs your attention", message, kind)
        # An older Claude sends no type at all: reported, because a missed
        # "waiting for you" is worse than a duplicate.
        self.assertIsNotNone(
            agent_notify.compose_notification({"hook_event_name": "Notification", "cwd": "/r/a"}, env)
        )

    def test_structured_details_carry_the_safe_fields_and_nothing_else(self):
        payload = {
            "hook_event_name": "PermissionRequest",
            "cwd": "/repos/logics-manager",
            "tool_name": "Bash",
            "tool_use_id": "toolu_01ABC",
            "tool_input": {"command": "rm -rf /tmp/build", "description": "Clean the build"},
            "permission_category": "shell_command",
            "model": "claude-opus-5",
            "transcript_path": "/home/u/.claude/projects/x/transcript.jsonl",
            "session_id": "abc123",
            "turn_id": "turn-9",
        }
        details = agent_notify.structured_details(payload, {agent_notify.SESSION_ENV: "work1"})
        self.assertEqual(details["session"], "work1")
        self.assertEqual(details["project"], "logics-manager")
        self.assertEqual(details["event"], "permissionrequest")
        self.assertEqual(details["tool"], "Bash")
        self.assertEqual(details["category"], "shell_command")
        self.assertEqual(details["model"], "claude-opus-5")
        # The command line, the transcript and the provider's own identifiers
        # never cross: this is the privacy boundary, asserted on the whole blob
        # rather than field by field so a new leak has to defeat the test.
        blob = json.dumps(details)
        for secret in ("rm -rf", "toolu_01ABC", "transcript.jsonl", "abc123", "turn-9"):
            self.assertNotIn(secret, blob)

    def test_a_permission_reason_needs_the_preview_opt_in(self):
        payload = {
            "hook_event_name": "PermissionRequest",
            "tool_input": {"command": "rm -rf /tmp", "description": "Clean the build"},
        }
        env = {agent_notify.SESSION_ENV: "work1"}
        self.assertNotIn("reason", agent_notify.structured_details(payload, env))
        opted = agent_notify.structured_details(payload, {**env, agent_notify.PREVIEW_ENV: "1"})
        self.assertEqual(opted["reason"], "Clean the build")
        # Only the description, never the command beside it.
        self.assertNotIn("rm -rf", json.dumps(opted))

    def test_a_stop_carries_its_reason_and_opted_in_preview(self):
        payload = {
            "hook_event_name": "Stop",
            "cwd": "/r/a",
            "stop_reason": "max_tokens",
            "last_assistant_message": "Here it is",
        }
        env = {agent_notify.SESSION_ENV: "work1", agent_notify.PREVIEW_ENV: "1"}
        details = agent_notify.structured_details(payload, env)
        self.assertEqual(details["stop_reason"], "max_tokens")
        self.assertEqual(details["preview"], "Here it is")
        self.assertNotIn("preview", agent_notify.structured_details(payload, {agent_notify.SESSION_ENV: "work1"}))

    def test_a_failed_turn_never_reads_as_a_completed_one(self):
        env = {agent_notify.SESSION_ENV: "work1"}
        title, message = agent_notify.compose_notification(
            {"hook_event_name": "StopFailure", "cwd": "/repos/logics-manager",
             "error_type": "billing_error", "error_message": "Credit exhausted"},
            env,
        )
        # The mark is read before the words are.
        self.assertTrue(title.startswith("✕"), title)
        self.assertNotIn("complete", message)
        self.assertIn("billing_error", message)
        self.assertIn("needs you", message)

    def test_a_transient_failure_reads_differently_from_one_needing_action(self):
        env = {agent_notify.SESSION_ENV: "work1"}
        transient = agent_notify.compose_notification(
            {"hook_event_name": "StopFailure", "error_type": "rate_limit"}, env,
        )[1]
        actionable = agent_notify.compose_notification(
            {"hook_event_name": "StopFailure", "error_type": "authentication_failed"}, env,
        )[1]
        self.assertIn("interrupted", transient)
        self.assertNotIn("needs you", transient)
        self.assertIn("needs you", actionable)

    def test_an_unknown_error_class_is_treated_as_needing_attention(self):
        """A failure this build has never seen is not one to reassure about."""
        message = agent_notify.compose_notification(
            {"hook_event_name": "StopFailure", "error_type": "something_new"},
            {agent_notify.SESSION_ENV: "work1"},
        )[1]
        self.assertIn("needs you", message)

    def test_a_failure_message_follows_the_preview_opt_in(self):
        payload = {"hook_event_name": "StopFailure", "error_type": "rate_limit",
                   "error_message": "Try again in 5 minutes"}
        env = {agent_notify.SESSION_ENV: "work1"}
        self.assertNotIn("Try again", agent_notify.compose_notification(payload, env)[1])
        opted = agent_notify.compose_notification(payload, {**env, agent_notify.PREVIEW_ENV: "1"})[1]
        self.assertIn("Try again in 5 minutes", opted)
        details = agent_notify.structured_details(payload, {**env, agent_notify.PREVIEW_ENV: "1"})
        self.assertEqual(details["error_type"], "rate_limit")
        self.assertEqual(details["preview"], "Try again in 5 minutes")
        # The class is safe metadata and crosses whatever the preview says.
        self.assertEqual(
            agent_notify.structured_details(payload, env)["error_type"], "rate_limit",
        )

    def test_each_event_produces_exactly_one_kind(self):
        """A failed turn produces no completion alert and a completed turn no
        failure alert, including when a provider fires both for one turn."""
        kinds = {
            "Stop": "complete",
            "StopFailure": "failed",
            "PermissionRequest": "attention",
            "Notification": "attention",
        }
        for event, expected in kinds.items():
            self.assertEqual(agent_notify.alert_kind({"hook_event_name": event}), expected, event)

    def test_a_permission_request_never_writes_to_stdout(self):
        # Claude Code reads this process's stdout as the decision for the tool
        # call. Anything printed here allows or denies it.
        written = []
        # The spawn double matters as much as the assertion: without it this
        # test raises a real desktop notification on the machine running it,
        # every run, which is how it was first noticed.
        calls = []
        for payload in (
            {"hook_event_name": "PermissionRequest", "tool_name": "Bash"},
            {"hook_event_name": "PermissionRequest"},
            "not json at all",
        ):
            text = payload if isinstance(payload, str) else json.dumps(payload)
            ctx = self._ctx(text, {agent_notify.SESSION_ENV: "work1"}, calls)
            ctx["out"] = written.append
            self.assertEqual(agent_notify.handle_notify([], ctx), 0)
        self.assertEqual(written, [])

    def test_permission_tool_name_is_sanitized_and_bounded(self):
        tool_name = "Bash\nwith\x00control " + "x" * 100
        _, message = agent_notify.compose_notification(
            {"hook_event_name": "PermissionRequest", "tool_name": tool_name},
            {agent_notify.SESSION_ENV: "work1"},
        )
        displayed = message.rsplit("(", 1)[1][:-1]
        self.assertEqual(displayed, "Bash with control " + "x" * 61 + "…")
        self.assertLessEqual(len(displayed), agent_notify._TOOL_NAME_LIMIT)

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

    def test_direct_notify_explains_setup(self):
        output = []
        self.assertEqual(agent_notify.handle_notify([], {"stdin_is_tty": True, "env": {}, "out": output.append}), 0)
        self.assertIn("cdx set <name> --notify on", "".join(output))

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

    def test_codex_goes_through_a_plugin_because_a_hooks_file_is_never_read(self):
        calls = []

        def spawn_sync(command, args, options):
            calls.append([command, *args])
            # Codex records the install in its own config; that is what we read back.
            with open(os.path.join(self.home, "config.toml"), "a", encoding="utf-8") as handle:
                handle.write('\n[plugins."cdx-notify@cdx"]\nenabled = true\n')
            return {"status": 0}

        with mock.patch.object(agent_notify, "notification_channel", return_value="osascript"):
            self.assertTrue(agent_notify.provision(self.home, "codex", True, self.env, spawn_sync))

        # The plugin root has to be somewhere writable. Deriving it by walking two
        # levels up from the home lands on `/` for anything not laid out as
        # `<base>/profiles/<name>`, which is how this first failed on Linux.
        self.assertTrue(os.access(os.path.dirname(agent_notify.codex_plugin_root(self.home)), os.W_OK))
        self.assertEqual(calls[0][:3], ["codex", "plugin", "marketplace"])
        self.assertEqual(calls[1], ["codex", "plugin", "add", "cdx-notify@cdx"])
        # The "hooks" key is what makes Codex load the file at all.
        root = agent_notify.codex_plugin_root(self.home)
        # Outside CODEX_HOME: a marketplace rooted inside it installs and never runs.
        self.assertFalse(root.startswith(self.home + os.sep))
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["hooks"], "./hooks/cdx-hooks.json")
        with open(agent_notify.hook_config_path(self.home, "codex"), encoding="utf-8") as handle:
            hooks = json.load(handle)["hooks"]
        self.assertIn("Stop", hooks)
        self.assertIn("PermissionRequest", hooks)
        # A free-standing hooks file at the Codex home root is never read, so we
        # must not leave one there pretending otherwise.
        self.assertFalse(os.path.exists(os.path.join(self.home, "hooks.json")))

    def test_codex_plugin_is_installed_once(self):
        calls = []

        def spawn_sync(command, args, options):
            calls.append(args)
            with open(os.path.join(self.home, "config.toml"), "a", encoding="utf-8") as handle:
                handle.write('\n[plugins."cdx-notify@cdx"]\nenabled = true\n')
            return {"status": 0}

        with mock.patch.object(agent_notify, "notification_channel", return_value="osascript"):
            agent_notify.provision(self.home, "codex", True, self.env, spawn_sync)
            before = len(calls)
            self.assertFalse(agent_notify.provision(self.home, "codex", True, self.env, spawn_sync))
        self.assertEqual(len(calls), before)

    def test_codex_plugin_is_removed_when_notifications_are_turned_off(self):
        with open(os.path.join(self.home, "config.toml"), "w", encoding="utf-8") as handle:
            handle.write('[plugins."cdx-notify@cdx"]\nenabled = true\n')
        calls = []
        agent_notify.provision(self.home, "codex", False, self.env,
                               lambda command, args, options: calls.append(args) or {"status": 0})
        self.assertIn(["plugin", "remove", "cdx-notify@cdx"], calls)

    def test_a_failing_codex_never_fails_the_launch(self):
        def spawn_sync(command, args, options):
            raise OSError("codex not found")

        with mock.patch.object(agent_notify, "notification_channel", return_value="osascript"):
            self.assertFalse(agent_notify.provision(self.home, "codex", True, self.env, spawn_sync))

    def test_installs_for_claude_under_its_own_home(self):
        self.assertTrue(self._provision("claude"))
        hooks = self._read("claude")["hooks"]
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], "/usr/local/bin/cdx notify")
        self.assertIn("Notification", hooks)

    def test_both_providers_subscribe_the_same_two_events(self):
        # The contract Codex has always used and Claude Code now publishes too.
        # Claude keeps Notification on top, for the waiting states nothing else
        # reports, and StopFailure, which Codex documents no equivalent of.
        self.assertTrue(self._provision("claude"))
        claude = set(self._read("claude")["hooks"])
        self.assertEqual(claude, {"Stop", "StopFailure", "Notification", "PermissionRequest"})

        calls = []
        with mock.patch.object(agent_notify, "notification_channel", return_value="osascript"):
            agent_notify.provision(self.home, "codex", True, self.env, lambda *a, **k: calls.append(a) or {"status": 0})
        plugin = os.path.join(
            agent_notify.codex_plugin_root(self.home, None), "hooks", "cdx-hooks.json"
        )
        with open(plugin, encoding="utf-8") as handle:
            codex = set(json.load(handle)["hooks"])
        self.assertEqual(codex, {"Stop", "PermissionRequest"})
        self.assertTrue(codex <= claude, "the shared contract is the smaller of the two")

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

    def test_notifications_are_off_until_asked_for(self):
        # Provisioning writes into the provider's own config and, on Codex, asks
        # the user to approve a hook: not something to do unrequested.
        self.assertFalse(agent_notify.notifications_enabled({"name": "a"}))
        self.assertFalse(agent_notify.notifications_enabled({"name": "a", "launch": {}}))
        self.assertFalse(agent_notify.notifications_enabled({"name": "a", "launch": {"notify": False}}))
        self.assertTrue(agent_notify.notifications_enabled({"name": "a", "launch": {"notify": True}}))

    def test_launch_env_carries_the_session_and_the_suppression(self):
        # CDX_HOME rides along too: a session runs with HOME redirected into its
        # own profile, so a hook that inherited the default would resolve a
        # different store than the tray companion writes into.
        session = {"name": "work1", "launch": {"notify_preview": True}}
        home = {"CDX_HOME": "/somewhere/.cdx"}
        self.assertEqual(
            agent_notify.launch_notify_env(session, True, env=home),
            {agent_notify.SESSION_ENV: "work1", agent_notify.PREVIEW_ENV: "1", **home},
        )
        self.assertEqual(
            agent_notify.launch_notify_env(session, False, env=home),
            {agent_notify.SESSION_ENV: "work1", agent_notify.ENABLED_ENV: "0", **home},
        )


if __name__ == "__main__":
    unittest.main()
