import urllib.error
import unittest
from unittest import mock

from src.update_check import (
    LatestReleaseCheckError,
    fetch_latest_release_or_raise,
    _fetch_latest_release,
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
