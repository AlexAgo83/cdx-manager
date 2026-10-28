import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from src import agent_notify, agent_state
from src.session_service import create_session_service
from src.tray_alerts import set_alerts


class AgentStateHookTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.service = create_session_service({"base_dir": self.base_dir})
        self.service["create_session"]("work", "claude")
        self.calls = []
        # A fixed channel: CI hosts have no desktop session, so the real lookup finds none there.
        channel = mock.patch("src.notify.notification_channel", return_value="notify-send")
        channel.start()
        self.addCleanup(channel.stop)

    def _notify(self, payload, preview=False):
        env = {agent_notify.SESSION_ENV: "work", agent_state.PID_ENV: str(os.getpid())}
        if preview:
            env[agent_notify.PREVIEW_ENV] = "1"
        written = []
        ctx = {
            "prompt_stdin": io.StringIO(json.dumps(payload)),
            "stdin_is_tty": False,
            "env": env,
            "cwd": "/repos/crh-manager",
            "service": self.service,
            "out": written.append,
            # Never the real notifier: see test_agent_notify_py.
            "spawn_sync": lambda argv, **kwargs: self.calls.append(argv),
        }
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(agent_notify.handle_notify([], ctx), 0)
        # A PermissionRequest reads stdout as the decision; nothing may reach it.
        self.assertEqual((written, stdout.getvalue()), ([], ""))
        return agent_state._read(os.path.join(agent_state.state_dir(self.base_dir), "work.json"))

    def test_a_turn_walks_through_working_waiting_and_done(self):
        record = self._notify({"hook_event_name": "UserPromptSubmit", "prompt": "fix the build"})
        self.assertEqual(record["state"], "working")
        self.assertEqual(record["provider"], "claude")
        self.assertEqual(record["project"], "crh-manager")
        self.assertEqual(record["pid"], os.getpid())
        # Prompt text is free text: kept only under the preview opt-in.
        self.assertIsNone(record["prompt"])

        record = self._notify({"hook_event_name": "PermissionRequest", "tool_name": "Bash"})
        self.assertEqual((record["state"], record["reason"]), ("waiting", "permission (Bash)"))

        record = self._notify({"hook_event_name": "Stop"})
        self.assertEqual((record["state"], record["reason"]), ("done", None))
        # Alerts still go out for the two events that raise one, the prompt excluded.
        self.assertEqual(len(self.calls), 2)

    def test_prompt_head_is_kept_under_the_preview_opt_in(self):
        record = self._notify({"hook_event_name": "UserPromptSubmit", "prompt": "fix\nthe " + "x" * 300}, preview=True)
        self.assertTrue(record["prompt"].startswith("fix the x"))
        self.assertLessEqual(len(record["prompt"]), agent_state._PROMPT_LIMIT)
        # It survives the rest of the turn.
        self.assertTrue(self._notify({"hook_event_name": "Stop"})["prompt"].startswith("fix the"))

    def test_a_prompt_raises_no_alert(self):
        self._notify({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})
        self.assertEqual(self.calls, [])

    def test_muted_alerts_still_record(self):
        set_alerts(self.base_dir, False)
        self.assertEqual(self._notify({"hook_event_name": "Stop"})["state"], "done")
        self.assertEqual(self.calls, [])

    def test_state_only_session_records_without_alerting(self):
        self.service["set_launch_settings"]("work", {"agent_state": True})
        self.assertEqual(self._notify({"hook_event_name": "Stop"})["state"], "done")
        self.assertEqual(self.calls, [])

    def test_limit_needs_the_provider_and_the_account_to_agree(self):
        failure = {"hook_event_name": "StopFailure", "error_type": "rate_limit"}
        spent = {"remaining_5h_pct": 0, "reset_at": "2026-10-28T18:00:00+00:00"}
        with mock.patch("src.commands.runs._status_row_for", return_value=spent):
            record = self._notify(failure)
        self.assertEqual((record["state"], record["reset_at"]), ("limit", "2026-10-28T18:00:00+00:00"))

        # The provider's word alone is a guess: a healthy account stays failed.
        with mock.patch("src.commands.runs._status_row_for", return_value={"remaining_5h_pct": 40}):
            record = self._notify(failure)
        self.assertEqual((record["state"], record["reason"], record["reset_at"]), ("failed", "rate_limit", None))

        # And an exhausted account does not turn an unrelated failure into a limit.
        with mock.patch("src.commands.runs._status_row_for", return_value=spent):
            record = self._notify({"hook_event_name": "StopFailure", "error_type": "invalid_request"})
        self.assertEqual(record["state"], "failed")

    def test_unsafe_session_names_write_nothing(self):
        ctx = {"service": {"base_dir": self.base_dir}}
        self.assertIsNone(agent_state.record(ctx, "../evil", {}, "stop", "", "/r", {}))
        self.assertFalse(os.path.exists(agent_state.state_dir(self.base_dir)))


class AgentListingTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)

    def _write(self, name, state, minutes_ago, pid=None):
        directory = agent_state.state_dir(self.base_dir)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, f"{name}.json"), "w", encoding="utf-8") as handle:
            json.dump({
                "session": name, "state": state, "pid": pid,
                "updated_at": (self.now - timedelta(minutes=minutes_ago)).isoformat(),
            }, handle)

    def test_waiting_first_stale_dropped_dead_marked_ended(self):
        self._write("fresh", "working", 1)
        self._write("asking", "waiting", 30)
        self._write("old", "done", 60 * 30)
        self._write("gone", "working", 5, pid=999999)
        agents = agent_state.list_agents(self.base_dir, 24, now=self.now, is_running=lambda pid: False)
        self.assertEqual([a["session"] for a in agents], ["asking", "fresh", "gone"])
        self.assertEqual((agents[2]["state"], agents[2]["last_state"]), ("ended", "working"))
        self.assertFalse(os.path.exists(os.path.join(agent_state.state_dir(self.base_dir), "old.json")))

    def test_cdx_agents_json(self):
        self._write("asking", "waiting", 0)
        output = []
        ctx = {"service": {"base_dir": self.base_dir}, "out": output.append}
        self.assertEqual(agent_state.handle_agents(["--json", "--max-age-hours", "100000"], ctx), 0)
        payload = json.loads("".join(output))
        self.assertEqual((payload["action"], payload["max_age_hours"]), ("agents", 100000))
        self.assertEqual(payload["agents"][0]["session"], "asking")


class StateProvisioningTests(unittest.TestCase):
    def test_state_installs_hooks_where_no_alert_could_be_shown(self):
        home = tempfile.mkdtemp()
        env = {"CDX_BIN": "/usr/local/bin/cdx", "PATH": ""}
        with mock.patch.object(agent_notify, "notification_channel", return_value=None):
            self.assertFalse(agent_notify.provision(home, "claude", True, env))
            self.assertTrue(agent_notify.provision(home, "claude", True, env, keep_state=True))


if __name__ == "__main__":
    unittest.main()
