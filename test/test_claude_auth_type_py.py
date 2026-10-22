import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from src import claude_credentials
from src.status_view import _format_status_detail, _format_status_rows

FULL = {"claudeAiOauth": {"accessToken": "a", "refreshToken": "r", "scopes": ["user:inference", "user:profile"]}}
INFERENCE_ONLY = {"claudeAiOauth": {"accessToken": "a", "scopes": ["user:inference"]}}


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def _setup_token(home):
    _write(os.path.join(home, "credentials", "default.json"), {"type": "oauth_token", "access_token": "tok"})


def _login_file(home, data):
    _write(os.path.join(home, ".claude", ".credentials.json"), data)


def _session(home):
    return {"name": "work", "provider": "claude", "authHome": home}


class FullLoginDetectionTests(unittest.TestCase):
    def test_shape_checks(self):
        self.assertTrue(claude_credentials.is_full_claude_login(FULL))
        self.assertTrue(claude_credentials.is_full_claude_login(
            {"claudeAiOauth": {"accessToken": "a", "scopes": ["user:inference", "user:mcp_servers"]}}))
        self.assertTrue(claude_credentials.is_full_claude_login(
            {"claudeAiOauth": {"accessToken": "a", "refreshToken": "r"}}))
        self.assertFalse(claude_credentials.is_full_claude_login(INFERENCE_ONLY))
        self.assertFalse(claude_credentials.is_full_claude_login({"claudeAiOauth": {"refreshToken": "r"}}))
        self.assertFalse(claude_credentials.is_full_claude_login({}))
        self.assertFalse(claude_credentials.is_full_claude_login(None))

    @unittest.skipIf(sys.platform == "win32", "the macOS keychain path imports pwd")
    def test_macos_keychain_lookup_uses_profile_entry(self):
        home = "/profiles/work"
        _, service = claude_credentials._keychain_identity(home)
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps(FULL), stderr="")
        with mock.patch("src.claude_credentials.sys.platform", "darwin"), \
                mock.patch("src.claude_credentials.subprocess.run", return_value=completed) as run:
            self.assertTrue(claude_credentials.has_full_claude_login(home))
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ["/usr/bin/security", "find-generic-password"])
        self.assertIn(service, argv)
        self.assertTrue(service.startswith("Claude Code-credentials-"))

    @unittest.skipIf(sys.platform == "win32", "the macOS keychain path imports pwd")
    def test_locked_keychain_is_not_a_login(self):
        with mock.patch("src.claude_credentials.sys.platform", "darwin"), \
                mock.patch("src.claude_credentials.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 51, stdout="", stderr="")):
            self.assertFalse(claude_credentials.has_full_claude_login("/profiles/work"))


class AuthTypeTests(unittest.TestCase):
    def test_auth_type(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(claude_credentials.claude_auth_type(home))
            _setup_token(home)
            self.assertEqual(claude_credentials.claude_auth_type(home), "setup-token")
            _login_file(home, FULL)
            self.assertEqual(claude_credentials.claude_auth_type(home), "full-login")

    def test_status_row_carries_auth_type_for_claude_only(self):
        from src.session_status import _status_row_from_session
        with tempfile.TemporaryDirectory() as home, mock.patch("src.session_status._session_runtime", return_value=None):
            _setup_token(home)
            base = {"name": "work", "provider": "claude", "authHome": home}
            self.assertEqual(_status_row_from_session({}, base)["auth_type"], "setup-token")
            self.assertIsNone(_status_row_from_session({}, {**base, "provider": "codex"})["auth_type"])

    def test_table_and_detail_show_type_only_when_known(self):
        row = {"session_name": "work", "provider": "claude", "enabled": True, "auth_status": "authenticated",
               "auth_type": "setup-token"}
        table = _format_status_rows([row])
        self.assertIn("TYPE", table)
        self.assertIn("setup-token", table)
        self.assertIn("Auth type: setup-token", _format_status_detail(row))
        plain = {**row, "auth_type": None}
        self.assertNotIn("TYPE", _format_status_rows([plain]))
        self.assertNotIn("Auth type", _format_status_detail(plain))


if __name__ == "__main__":
    unittest.main()


class SetupTokenExpiryTests(unittest.TestCase):
    def _token(self, home, **extra):
        _write(os.path.join(home, "credentials", "default.json"), {"access_token": "tok", **extra})

    def test_created_at_sets_the_expiry_and_mtime_is_the_fallback(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(claude_credentials.setup_token_days_left(home))
            self._token(home, created_at="2026-01-01T00:00:00+00:00")
            now = claude_credentials.setup_token_expires_at(home) - 10 * 86400
            self.assertEqual(claude_credentials.setup_token_days_left(home, now=now), 10)
            self._token(home)
            # Clock passed explicitly: Windows can stamp mtime a hair after time.time().
            minted = os.path.getmtime(os.path.join(home, "credentials", "default.json"))
            self.assertEqual(claude_credentials.setup_token_days_left(home, now=minted + 3600), 364)

    def test_status_and_doctor_warn_only_when_renewal_is_due(self):
        from src.health import _claude_setup_token_issues
        from src.status_view import _auth_type_label
        self.assertEqual(_auth_type_label({"auth_type": "setup-token", "auth_expires_in_days": 200}), ("setup-token", False))
        self.assertEqual(_auth_type_label({"auth_type": "setup-token", "auth_expires_in_days": 12}), ("setup-token 12d", True))
        self.assertEqual(_auth_type_label({"auth_type": "setup-token", "auth_expires_in_days": -1}), ("setup-token expired", True))
        with tempfile.TemporaryDirectory() as home:
            self._token(home, created_at="2025-11-01T00:00:00+00:00")
            with mock.patch("src.claude_credentials.peek_keychain_credentials", return_value=None), \
                    mock.patch("src.claude_credentials.setup_token_days_left", return_value=5):
                issues = _claude_setup_token_issues({"name": "work", "authHome": home})
        self.assertEqual(issues[0]["code"], "claude_setup_token_expiry")
        self.assertIn("cdx login work", issues[0]["message"])
