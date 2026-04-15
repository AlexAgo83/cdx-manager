import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest import mock

from src import claude_usage
from src import cli


class _Response:
    def __init__(self, headers):
        self._headers = headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getheaders(self):
        return list(self._headers.items())


class RuntimePythonTests(unittest.TestCase):
    def format_local_reset(self, unix_seconds):
        dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc).astimezone()
        return f"{dt.strftime('%b')} {dt.day} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}"

    def test_fetch_claude_rate_limit_headers_from_success_response(self):
        headers = {
            "anthropic-ratelimit-unified-5h-utilization": "0.19",
            "anthropic-ratelimit-unified-5h-reset": "1776464880",
            "anthropic-ratelimit-unified-7d-utilization": "0.25",
            "anthropic-ratelimit-unified-7d-reset": "1777065600",
        }
        with mock.patch("urllib.request.urlopen", return_value=_Response(headers)):
            result = claude_usage.fetch_claude_rate_limit_headers("token")
        self.assertEqual(result["remaining_5h_pct"], 81)
        self.assertEqual(result["remaining_week_pct"], 75)
        self.assertEqual(result["reset_5h_at"], self.format_local_reset(1776464880))
        self.assertEqual(result["reset_week_at"], self.format_local_reset(1777065600))
        self.assertEqual(result["reset_at"], self.format_local_reset(1777065600))
        self.assertEqual(
            datetime.fromisoformat(result["updated_at"]).utcoffset(),
            datetime.now().astimezone().utcoffset(),
        )

    def test_fetch_claude_rate_limit_headers_from_http_error_headers(self):
        headers = {
            "anthropic-ratelimit-unified-5h-utilization": "0.50",
            "anthropic-ratelimit-unified-5h-reset": "1776464880",
        }
        error = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=429,
            msg="rate limited",
            hdrs=headers,
            fp=None,
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            result = claude_usage.fetch_claude_rate_limit_headers("token")
        self.assertEqual(result["remaining_5h_pct"], 50)
        self.assertIsNone(result["remaining_week_pct"])
        self.assertEqual(result["reset_5h_at"], self.format_local_reset(1776464880))
        self.assertIsNone(result["reset_week_at"])
        self.assertEqual(result["reset_at"], self.format_local_reset(1776464880))

    def test_fetch_claude_rate_limit_headers_returns_none_on_url_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            self.assertIsNone(claude_usage.fetch_claude_rate_limit_headers("token"))

    def test_refresh_claude_session_status_without_credentials_returns_none(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            self.assertIsNone(claude_usage.refresh_claude_session_status({"authHome": temp_dir}))

    def test_refresh_claude_session_status_reads_credentials(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, ".claude")
            os.makedirs(cred_dir, exist_ok=True)
            with open(os.path.join(cred_dir, ".credentials.json"), "w", encoding="utf-8") as handle:
                json.dump({"claudeAiOauth": {"accessToken": "secret"}}, handle)
            with mock.patch("src.claude_usage.fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 77}) as fetch:
                result = claude_usage.refresh_claude_session_status({"authHome": temp_dir})
            fetch.assert_called_once_with("secret")
            self.assertEqual(result["remaining_5h_pct"], 77)

    def test_rotate_log_if_needed_truncates_large_file(self):
        with tempfile.TemporaryDirectory(prefix="cdx-log-") as temp_dir:
            log_path = os.path.join(temp_dir, "cdx-session.log")
            with open(log_path, "wb") as handle:
                handle.write(b"x" * cli.LOG_ROTATE_BYTES)
            cli._rotate_log_if_needed(log_path)
            self.assertEqual(os.path.getsize(log_path), 0)


if __name__ == "__main__":
    unittest.main()
