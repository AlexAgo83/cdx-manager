import unittest
from unittest import mock

from src.notify import parse_notify_args, send_desktop_notification


class NotifyPythonTests(unittest.TestCase):
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
