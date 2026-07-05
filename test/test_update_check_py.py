import tempfile
import unittest
import urllib.error
from unittest import mock

from src.update_check import (
    LatestReleaseCheckError,
    _fetch_latest_release,
    _format_fetch_error,
    check_for_update,
    check_logics_manager_for_update,
    fetch_latest_logics_manager_version,
    fetch_latest_release,
    fetch_latest_release_or_raise,
    is_newer_version,
)


class UpdateCheckPythonTests(unittest.TestCase):
    def test_fetch_latest_release_uses_github_token_when_available(self):
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"tag_name":"v1.2.3","html_url":"https://example.test/release"}'

        def open_url(request, timeout=None):
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return Response()

        with mock.patch("src.update_check.urllib.request.urlopen", side_effect=open_url):
            latest = _fetch_latest_release(env={"GH_TOKEN": "secret-token"})

        self.assertEqual(latest["latest_version"], "1.2.3")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret-token")
        self.assertEqual(captured["timeout"], 5)

    def test_fetch_latest_release_or_raise_describes_rate_limit(self):
        error = urllib.error.HTTPError(
            url="https://api.github.com/repos/AlexAgo83/cdx-manager/releases/latest",
            code=403,
            msg="rate limit",
            hdrs=None,
            fp=None,
        )

        with mock.patch("src.update_check.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(LatestReleaseCheckError, "rate limit"):
                fetch_latest_release_or_raise()

    def test_version_comparison_rejects_invalid_versions(self):
        self.assertTrue(is_newer_version("1.2.3", "1.2.4"))
        self.assertFalse(is_newer_version("1.2.3", "1.2.3"))
        self.assertFalse(is_newer_version("1.2", "1.2.4"))
        self.assertFalse(is_newer_version("1.2.3", "latest"))

    def test_check_for_update_uses_fresh_cache(self):
        with tempfile.TemporaryDirectory(prefix="cdx-update-check-") as temp_dir:
            with mock.patch("src.update_check.fetch_latest_release") as fetch:
                fetch.return_value = {"latest_version": "1.2.3", "url": "https://example.test/release"}
                first = check_for_update(temp_dir, "1.0.0", now_fn=lambda: 1000)
                second = check_for_update(temp_dir, "1.0.0", now_fn=lambda: 1001)
                third = check_for_update(temp_dir, "1.0.0", now_fn=lambda: 4600)

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(first["latest_version"], "1.2.3")
        self.assertFalse(first["cached"])
        self.assertEqual(second["latest_version"], "1.2.3")
        self.assertTrue(second["cached"])
        self.assertEqual(third["latest_version"], "1.2.3")
        self.assertFalse(third["cached"])

    def test_check_for_update_can_be_disabled(self):
        with tempfile.TemporaryDirectory(prefix="cdx-update-check-") as temp_dir:
            with mock.patch("src.update_check.fetch_latest_release") as fetch:
                result = check_for_update(
                    temp_dir,
                    "1.0.0",
                    env={"CDX_DISABLE_UPDATE_CHECK": "yes"},
                )

        self.assertIsNone(result)
        fetch.assert_not_called()

    def test_fetch_latest_release_returns_none_on_network_error(self):
        with mock.patch("src.update_check.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            self.assertIsNone(fetch_latest_release())

    def test_fetch_latest_logics_manager_version_uses_npm_package(self):
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"version":"2.4.0"}'

        def open_url(request, timeout=None):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return Response()

        with mock.patch("src.update_check.urllib.request.urlopen", side_effect=open_url):
            self.assertEqual(fetch_latest_logics_manager_version(), "2.4.0")

        self.assertIn("@grifhinz%2Flogics-manager", captured["url"])
        self.assertEqual(captured["timeout"], 1)

    def test_check_logics_manager_for_update_uses_installed_version_and_cache(self):
        with tempfile.TemporaryDirectory(prefix="cdx-logics-update-check-") as temp_dir:
            runner = mock.Mock(return_value=mock.Mock(returncode=0, stdout="logics-manager 2.3.0\n", stderr=""))
            with mock.patch("src.update_check.shutil.which", return_value="/usr/bin/logics-manager"):
                with mock.patch("src.update_check.fetch_latest_logics_manager_version", return_value="2.4.0") as fetch:
                    first = check_logics_manager_for_update(temp_dir, env={"PATH": "/usr/bin"}, now_fn=lambda: 1000, runner=runner)
                    second = check_logics_manager_for_update(temp_dir, env={"PATH": "/usr/bin"}, now_fn=lambda: 1001, runner=runner)
                    third = check_logics_manager_for_update(temp_dir, env={"PATH": "/usr/bin"}, now_fn=lambda: 4600, runner=runner)

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(first["tool"], "logics-manager")
        self.assertEqual(first["latest_version"], "2.4.0")
        self.assertEqual(first["current_version"], "2.3.0")
        self.assertEqual(first["update_command"], "logics-manager self-update")
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertFalse(third["cached"])

    def test_check_logics_manager_for_update_does_not_cache_a_failed_fetch(self):
        with tempfile.TemporaryDirectory(prefix="cdx-logics-update-check-") as temp_dir:
            runner = mock.Mock(return_value=mock.Mock(returncode=0, stdout="logics-manager 2.3.0\n", stderr=""))
            with mock.patch("src.update_check.shutil.which", return_value="/usr/bin/logics-manager"):
                with mock.patch("src.update_check.fetch_latest_logics_manager_version", side_effect=[None, "2.4.0"]) as fetch:
                    failed = check_logics_manager_for_update(temp_dir, env={"PATH": "/usr/bin"}, now_fn=lambda: 1000, runner=runner)
                    recovered = check_logics_manager_for_update(temp_dir, env={"PATH": "/usr/bin"}, now_fn=lambda: 1001, runner=runner)

        self.assertIsNone(failed)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(recovered["latest_version"], "2.4.0")
        self.assertFalse(recovered["cached"])

    def test_check_logics_manager_for_update_skips_when_cli_missing(self):
        with tempfile.TemporaryDirectory(prefix="cdx-logics-update-check-") as temp_dir:
            with mock.patch("src.update_check.shutil.which", return_value=None):
                result = check_logics_manager_for_update(temp_dir, env={"PATH": "/usr/bin"})
        self.assertIsNone(result)

    def test_fetch_error_messages_cover_common_failures(self):
        not_found = urllib.error.HTTPError("url", 404, "missing", None, None)
        server_error = urllib.error.HTTPError("url", 500, "server", None, None)
        offline = urllib.error.URLError("offline")

        self.assertIn("Unable to find", _format_fetch_error(not_found))
        self.assertIn("HTTP 500", _format_fetch_error(server_error))
        self.assertIn("offline", _format_fetch_error(offline))
        self.assertIn("Timed out", _format_fetch_error(TimeoutError()))
