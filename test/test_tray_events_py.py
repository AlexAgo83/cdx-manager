"""The hook-to-tray handoff.

Two failures matter more than everything else here, and they pull in opposite
directions: the user seeing the same alert twice, and the user seeing it not at
all. Every rule below exists to keep one of those from happening.
"""
import io
import json
import os
from unittest import mock

from cli_test_support import CliTestBase

from src import agent_notify
from src.agent_notify import SESSION_ENV, handle_notify
from src.cli import main
from src.errors import CdxError
from src.session_service import create_session_service
from src.tray_events import (
    HEARTBEAT_FRESH_SECONDS,
    MAX_SPOOLED_EVENTS,
    SCHEMA_VERSION,
    acknowledge,
    events_path,
    heartbeat_path,
    publish,
    read_events,
    tray_is_listening,
    write_heartbeat,
)


class HeartbeatTest(CliTestBase):
    def test_no_heartbeat_means_no_tray(self):
        self.assertFalse(tray_is_listening(self.make_temp_dir(), now=1000.0))

    def test_a_fresh_heartbeat_means_a_tray(self):
        base = self.make_temp_dir()
        write_heartbeat(base, pid=42, now=1000.0)
        self.assertTrue(tray_is_listening(base, now=1000.0 + 10))

    def test_the_window_is_wider_than_a_poll_period(self):
        """The tray beats once per poll — 60s across WSL. A window narrower than
        that reads a healthy tray as stale, and the user then gets the alert
        twice: once from the tray, once from the direct fallback."""
        self.assertGreater(HEARTBEAT_FRESH_SECONDS, 60)

    def test_a_stale_heartbeat_hands_the_alert_back(self):
        base = self.make_temp_dir()
        write_heartbeat(base, pid=42, now=1000.0)
        self.assertFalse(tray_is_listening(base, now=1000.0 + HEARTBEAT_FRESH_SECONDS + 1))

    def test_a_schema_this_cdx_cannot_speak_is_not_a_listener(self):
        """Publishing to a companion that cannot read the event would lose the
        notification outright; falling back merely delivers it the old way."""
        base = self.make_temp_dir()
        write_heartbeat(base, pid=42, now=1000.0)
        with open(heartbeat_path(base), "w", encoding="utf-8") as handle:
            json.dump({"schema": SCHEMA_VERSION + 1, "pid": 42, "at": 1000.0}, handle)
        self.assertFalse(tray_is_listening(base, now=1000.0))

    def test_a_damaged_heartbeat_reads_as_absent(self):
        base = self.make_temp_dir()
        os.makedirs(os.path.dirname(heartbeat_path(base)), exist_ok=True)
        with open(heartbeat_path(base), "w", encoding="utf-8") as handle:
            handle.write("{ truncated")
        self.assertFalse(tray_is_listening(base, now=1000.0))


class SpoolTest(CliTestBase):
    def _live(self, now=1000.0):
        base = self.make_temp_dir()
        write_heartbeat(base, pid=42, now=now)
        return base

    def test_publishing_requires_a_listening_tray(self):
        base = self.make_temp_dir()
        self.assertFalse(publish(base, "t", "m", now=1000.0))
        self.assertEqual(read_events(base), [])

    def test_a_published_event_is_readable_once(self):
        base = self._live()
        self.assertTrue(publish(base, "✓ work", "repo · turn complete", now=1000.0))
        events = read_events(base)
        self.assertEqual(len(events), 1)
        acknowledge(base, [events[0]["id"]], now=1001.0)
        self.assertEqual(read_events(base), [])

    def test_concurrent_hooks_do_not_lose_each_other(self):
        """Several sessions can finish at the same instant. An append is atomic;
        a read-modify-write of one JSON array would drop all but one, and the
        losers are notifications nobody ever gets."""
        base = self._live()
        for index in range(5):
            publish(base, f"✓ s{index}", "m", now=1000.0, event_id=f"e{index}")
        self.assertEqual(len(read_events(base)), 5)

    def test_acknowledging_twice_is_not_an_error(self):
        """The tray can crash between showing an event and acknowledging it, so
        the second attempt has to be harmless."""
        base = self._live()
        publish(base, "t", "m", now=1000.0, event_id="e1")
        first = acknowledge(base, ["e1"], now=1001.0)
        second = acknowledge(base, ["e1"], now=1002.0)
        self.assertEqual(first["acknowledged"], 1)
        self.assertEqual(second["acknowledged"], 0)

    def test_acknowledging_an_unknown_id_changes_nothing(self):
        base = self._live()
        publish(base, "t", "m", now=1000.0, event_id="e1")
        acknowledge(base, ["never-existed"], now=1001.0)
        self.assertEqual(len(read_events(base)), 1)

    def test_a_partial_last_line_is_skipped_not_fatal(self):
        """The writer is a provider hook that can be killed mid-append, so half
        a line is an expected state rather than corruption."""
        base = self._live()
        publish(base, "t", "m", now=1000.0, event_id="e1")
        with open(events_path(base), "a", encoding="utf-8") as handle:
            handle.write('{"id": "e2", "title": "trunc')
        events = read_events(base)
        self.assertEqual([event["id"] for event in events], ["e1"])

    def test_the_spool_keeps_the_newest_when_it_overflows(self):
        """A tray down for an hour must not flood the user on return, and an
        old alert is worth less than a new one."""
        base = self._live()
        for index in range(MAX_SPOOLED_EVENTS + 10):
            publish(base, "t", "m", now=1000.0, event_id=f"e{index:03d}")
        events = read_events(base)
        self.assertEqual(len(events), MAX_SPOOLED_EVENTS)
        self.assertEqual(events[-1]["id"], f"e{MAX_SPOOLED_EVENTS + 9:03d}")


class NotifyRoutingTest(CliTestBase):
    def _ctx(self, base_dir):
        return {
            "service": {"base_dir": base_dir},
            "env": {SESSION_ENV: "work"},
            "out": lambda _text: None,
            "stdin_is_tty": False,
            # A real stream: handle_notify reads it, and falling back to the
            # captured stdin under pytest raises inside the hook's guard.
            "prompt_stdin": io.StringIO(""),
            "spawn_sync": lambda *args, **kwargs: None,
        }

    def _notify(self, base_dir, payload):
        """Run the hook, reporting whether the direct path fired."""
        with mock.patch.object(agent_notify, "send_desktop_notification") as direct:
            handle_notify([payload], self._ctx(base_dir))
            return direct.called

    def test_without_a_tray_the_direct_path_is_untouched(self):
        base = self.make_temp_dir()
        fired = self._notify(base, '{"hook_event_name": "Stop", "cwd": "/tmp/repo"}')
        self.assertEqual(read_events(base), [])
        self.assertTrue(fired, "the direct notification path should have run")

    def test_a_live_tray_becomes_the_only_owner(self):
        """The point of the whole slice: one alert, not two."""
        base = self.make_temp_dir()
        write_heartbeat(base)
        fired = self._notify(base, '{"hook_event_name": "Stop", "cwd": "/tmp/repo"}')
        events = read_events(base)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "complete")
        self.assertFalse(fired, "the direct path must not also fire")

    def test_an_attention_event_is_labelled_as_one(self):
        base = self.make_temp_dir()
        write_heartbeat(base)
        self._notify(base, '{"hook_event_name": "Notification"}')
        self.assertEqual(read_events(base)[0]["kind"], "attention")

    def test_the_tray_never_receives_more_than_the_direct_path_would(self):
        """Publication sits below the composition boundary, so the tray gets the
        same sanitized text and cannot be handed what privacy rules removed."""
        base = self.make_temp_dir()
        write_heartbeat(base)
        self._notify(
            base,
            '{"hook_event_name": "Stop", "cwd": "/tmp/repo", "last_assistant_message": "SECRET"}',
        )
        self.assertNotIn("SECRET", json.dumps(read_events(base)))


class TrayEventCommandTest(CliTestBase):
    """The commands the companion uses instead of touching the spool itself.

    On a Windows host serving CDX from WSL, the spool is in the Linux
    filesystem and the tray runs on Windows. Going through `cdx` means the
    existing wsl.exe transport carries events too, with no path translation and
    no assumption that either side can see the other's disk.
    """

    def _service(self):
        temp_dir = self.make_temp_dir()
        return create_session_service({"base_dir": temp_dir}), temp_dir

    def _run(self, argv, service, temp_dir):
        io_obj = self.make_io()
        code = main(argv, {**io_obj, "service": service, "env": {"CDX_HOME": temp_dir}})
        return code, io_obj["stdout"].getvalue()

    def test_heartbeat_then_events_then_ack(self):
        service, temp_dir = self._service()
        self._run(["tray", "heartbeat"], service, temp_dir)
        self.assertTrue(tray_is_listening(temp_dir))

        publish(temp_dir, "✓ work", "repo · turn complete", event_id="e1")
        code, out = self._run(["tray", "events", "--json"], service, temp_dir)
        self.assertEqual(code, 0)
        events = json.loads(out)["events"]
        self.assertEqual([event["id"] for event in events], ["e1"])

        self._run(["tray", "ack", "e1"], service, temp_dir)
        _code, out = self._run(["tray", "events", "--json"], service, temp_dir)
        self.assertEqual(json.loads(out)["events"], [])

    def test_ack_without_an_id_is_refused(self):
        """Acknowledging nothing is a caller mistake, and silently succeeding
        would let a broken consumption loop look like a working one."""
        service, temp_dir = self._service()
        with self.assertRaises(CdxError):
            self._run(["tray", "ack"], service, temp_dir)

    def test_events_reads_empty_without_a_spool(self):
        service, temp_dir = self._service()
        code, out = self._run(["tray", "events", "--json"], service, temp_dir)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["events"], [])


class LaunchEnvironmentTest(CliTestBase):
    """The hook has to reach the same store the companion writes into.

    CDX_HOME defaults to `~/.cdx`, resolved against HOME — and a provider
    session runs with HOME redirected into its own profile, which is how cdx
    isolates auth. Inheriting the default would make a hook resolve a different
    store from the companion's, find no heartbeat, and deliver the notification
    itself. Nothing errors; the tray simply never receives anything.
    """

    def test_the_launch_environment_pins_cdx_home(self):
        from src.agent_notify import launch_notify_env
        session = {"name": "work", "launch": {}}
        values = launch_notify_env(session, True, env={"CDX_HOME": "/somewhere/.cdx"})
        self.assertEqual(values["CDX_HOME"], "/somewhere/.cdx")

    def test_it_is_pinned_for_headless_runs_too(self):
        """Headless runs share the session's home and therefore its hooks, so
        the same mismatch would apply."""
        from src.agent_notify import launch_notify_env
        session = {"name": "work", "launch": {}}
        values = launch_notify_env(session, False, env={"CDX_HOME": "/somewhere/.cdx"})
        self.assertEqual(values["CDX_HOME"], "/somewhere/.cdx")
        self.assertEqual(values["CDX_NOTIFY"], "0")


class AlertMuteTest(CliTestBase):
    """The quick way to go quiet, and what it deliberately does not do.

    Muting stops the banner, not the record: events keep reaching a running
    tray so the menu shows what was missed. And it applies to the direct path
    too, because otherwise quitting the companion would silently un-mute.
    """

    def _ctx(self, base_dir):
        return {
            "service": {"base_dir": base_dir},
            "env": {SESSION_ENV: "work"},
            "out": lambda _text: None,
            "stdin_is_tty": False,
            "prompt_stdin": io.StringIO(""),
            "spawn_sync": lambda *args, **kwargs: None,
        }

    def _notify(self, base_dir):
        with mock.patch.object(agent_notify, "send_desktop_notification") as direct:
            handle_notify(['{"hook_event_name": "Stop", "cwd": "/tmp/repo"}'], self._ctx(base_dir))
            return direct.called

    def test_alerts_are_on_until_muted(self):
        from src.tray_alerts import alerts_enabled
        self.assertTrue(alerts_enabled(self.make_temp_dir()))

    def test_a_damaged_state_file_does_not_silence_anyone(self):
        """A mute that outlived a damaged file would silence someone with no way
        to see why, and silence is the failure that hides itself."""
        from src.tray_alerts import alerts_enabled, state_path
        base = self.make_temp_dir()
        path = state_path(base)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ truncated")
        self.assertTrue(alerts_enabled(base))

    def test_muting_stops_the_direct_notification(self):
        from src.tray_alerts import set_alerts
        base = self.make_temp_dir()
        set_alerts(base, False)
        self.assertFalse(self._notify(base), "muted must not raise a banner")

    def test_muting_still_records_the_event_for_the_tray(self):
        from src.tray_alerts import set_alerts
        base = self.make_temp_dir()
        write_heartbeat(base)
        set_alerts(base, False)
        self.assertFalse(self._notify(base))
        self.assertEqual(len(read_events(base)), 1, "the menu should still show it")

    def test_unmuting_restores_delivery(self):
        from src.tray_alerts import set_alerts
        base = self.make_temp_dir()
        set_alerts(base, False)
        set_alerts(base, True)
        self.assertTrue(self._notify(base))
