import unittest
import subprocess
import time
from unittest import mock

from src.notify import parse_notify_args, schedule_notification_event, send_desktop_notification


class NotifyPythonTests(unittest.TestCase):
    def future_timestamp(self):
        return int(time.time()) + 1800

    def test_send_desktop_notification_dispatches_to_macos_osascript(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))

        with mock.patch("sys.platform", "darwin"):
            with mock.patch("src.notify.shutil_which", return_value="/usr/bin/osascript"):
                send_desktop_notification("Title", 'Hello "World"', spawn_sync=spawn_sync, env={"PATH": "/usr/bin"})

        self.assertEqual(calls[0][0][0], "osascript")
        self.assertEqual(calls[0][0][1], "-e")
        self.assertIn('display notification "Hello \\"World\\""', calls[0][0][2])
        self.assertEqual(calls[0][1]["timeout"], 5)

    def test_send_desktop_notification_falls_back_when_backend_missing(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil_which", return_value=None):
                send_desktop_notification("Title", "Body", spawn_sync=spawn_sync, env={"PATH": ""})

        self.assertEqual(calls, [])

    def test_send_desktop_notification_dispatches_to_linux_notify_send(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil_which", side_effect=lambda command, _env: command == "notify-send"):
                send_desktop_notification("Title; rm -rf /", "Body $(bad)", spawn_sync=spawn_sync, env={"PATH": "/usr/bin"})

        self.assertEqual(calls[0][0], ["notify-send", "Title; rm -rf /", "Body $(bad)"])
        self.assertEqual(calls[0][1]["timeout"], 5)

    def test_parse_notify_args_supports_poll_equals(self):
        parsed = parse_notify_args(["--next-ready", "--poll=5", "--once", "--json"])

        self.assertEqual(parsed["mode"], "next-ready")
        self.assertEqual(parsed["poll"], 5)
        self.assertTrue(parsed["once"])
        self.assertTrue(parsed["json"])
        self.assertFalse(parsed["refresh"])

    def test_parse_notify_args_supports_refresh(self):
        parsed = parse_notify_args(["--next-ready", "--refresh"])

        self.assertEqual(parsed["mode"], "next-ready")
        self.assertTrue(parsed["refresh"])

    def test_parse_notify_args_supports_schedule(self):
        parsed = parse_notify_args(["main", "--at-reset", "--schedule"])

        self.assertEqual(parsed["mode"], "at-reset")
        self.assertEqual(parsed["name"], "main")
        self.assertTrue(parsed["schedule"])

    def test_schedule_notification_event_uses_systemd_run_on_linux(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        parsed = parse_notify_args(["main", "--at-reset", "--schedule"])
        event = {
            "ready": False,
            "title": "cdx",
            "message": "Waiting for main reset",
            "session": "main",
            "target_timestamp": self.future_timestamp(),
        }

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil_which", side_effect=lambda command, _env: command == "systemd-run"):
                schedule = schedule_notification_event(
                    "/tmp/cdx",
                    parsed,
                    event,
                    spawn_sync=spawn_sync,
                    env={"PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                    now_fn=lambda: event["target_timestamp"] - 60,
                )

        self.assertTrue(schedule["scheduled"])
        self.assertEqual(schedule["backend"], "systemd")
        self.assertEqual(calls[0][0][0], "systemd-run")
        self.assertIn("--user", calls[0][0])
        self.assertIn("/usr/local/bin/cdx", calls[0][0])
        self.assertIn("--once", calls[0][0])
        self.assertIn("--refresh", calls[0][0])

    def test_schedule_notification_event_treats_existing_systemd_unit_as_success(self):
        def spawn_sync(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, "", "Unit already exists")

        parsed = parse_notify_args(["main", "--at-reset", "--schedule"])
        event = {
            "ready": False,
            "title": "cdx",
            "message": "Waiting for main reset",
            "session": "main",
            "target_timestamp": self.future_timestamp(),
        }

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil_which", side_effect=lambda command, _env: command == "systemd-run"):
                schedule = schedule_notification_event(
                    "/tmp/cdx",
                    parsed,
                    event,
                    spawn_sync=spawn_sync,
                    env={"PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                    now_fn=lambda: event["target_timestamp"] - 60,
                )

        self.assertTrue(schedule["scheduled"])
        self.assertTrue(schedule["existing"])
        self.assertEqual(schedule["backend"], "systemd")

    def test_schedule_notification_event_uses_macos_launchd(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        parsed = parse_notify_args(["main", "--at-reset", "--schedule"])
        event = {
            "ready": False,
            "title": "cdx",
            "message": "Waiting for main reset",
            "session": "main",
            "target_timestamp": self.future_timestamp(),
        }

        with self.subTest("darwin"):
            with mock.patch("sys.platform", "darwin"):
                with mock.patch("src.notify.os.path.expanduser", return_value="/tmp/cdx-home"):
                    with mock.patch("src.notify.os.getuid", return_value=501, create=True):
                        schedule = schedule_notification_event(
                            "/tmp/cdx",
                            parsed,
                            event,
                            spawn_sync=spawn_sync,
                            env={"PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                            now_fn=lambda: event["target_timestamp"] - 60,
                        )

        self.assertTrue(schedule["scheduled"])
        self.assertEqual(schedule["backend"], "launchd")
        self.assertEqual(calls[0][0][0], "launchctl")

    def test_schedule_notification_event_treats_existing_launchd_job_as_success(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 5, "", "Bootstrap failed: 5: Input/output error")

        parsed = parse_notify_args(["main", "--at-reset", "--schedule"])
        event = {
            "ready": False,
            "title": "cdx",
            "message": "Waiting for main reset",
            "session": "main",
            "target_timestamp": self.future_timestamp(),
        }

        with mock.patch("sys.platform", "darwin"):
            with mock.patch("src.notify.os.path.expanduser", return_value="/tmp/cdx-home"):
                with mock.patch("src.notify.os.getuid", return_value=501, create=True):
                    schedule = schedule_notification_event(
                        "/tmp/cdx",
                        parsed,
                        event,
                        spawn_sync=spawn_sync,
                        env={"PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                        now_fn=lambda: event["target_timestamp"] - 60,
                    )

        self.assertTrue(schedule["scheduled"])
        self.assertTrue(schedule["existing"])
        self.assertEqual(schedule["backend"], "launchd")
        self.assertEqual(len(calls), 1)

    def test_send_desktop_notification_swallows_macos_backend_errors(self):
        def spawn_sync(_argv, **_kwargs):
            raise FileNotFoundError("osascript")

        with mock.patch("sys.platform", "darwin"):
            with mock.patch("src.notify.shutil_which", return_value="/usr/bin/osascript"):
                send_desktop_notification("Title", "Body", spawn_sync=spawn_sync, env={"PATH": "/usr/bin"})

    def test_send_desktop_notification_swallows_windows_backend_errors(self):
        def spawn_sync(_argv, **_kwargs):
            raise FileNotFoundError("powershell")

        with mock.patch("sys.platform", "win32"):
            send_desktop_notification("Title", "Body", spawn_sync=spawn_sync, env={"PATH": ""})


if __name__ == "__main__":
    unittest.main()
