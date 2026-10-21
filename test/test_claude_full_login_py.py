import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from src import claude_credentials, provider_runtime
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

    def test_file_login_changes_launch_env(self):
        with tempfile.TemporaryDirectory() as home:
            _setup_token(home)
            _login_file(home, FULL)
            with mock.patch.dict(os.environ, {"ANTHROPIC_PROFILE": "inherited"}):
                spec = provider_runtime._build_launch_spec(_session(home), cwd=home)
        env = spec["options"]["env"]
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertNotIn("ANTHROPIC_PROFILE", env)

    def test_setup_token_only_keeps_today_env(self):
        with tempfile.TemporaryDirectory() as home:
            _setup_token(home)
            with mock.patch.dict(os.environ):
                os.environ.pop("ANTHROPIC_PROFILE", None)
                spec = provider_runtime._build_launch_spec(_session(home), cwd=home)
        env = spec["options"]["env"]
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "tok")
        self.assertEqual(env["ANTHROPIC_PROFILE"], "default")

    def test_inference_only_login_file_keeps_profile_env(self):
        with tempfile.TemporaryDirectory() as home:
            _setup_token(home)
            _login_file(home, INFERENCE_ONLY)
            env = provider_runtime._build_launch_spec(_session(home), cwd=home)["options"]["env"]
        self.assertEqual(env["ANTHROPIC_PROFILE"], "default")

    def test_macos_keychain_login_changes_launch_env(self):
        with tempfile.TemporaryDirectory() as home:
            _setup_token(home)
            with mock.patch("src.claude_credentials.read_keychain_credentials", return_value=FULL):
                env = provider_runtime._build_launch_spec(_session(home), cwd=home)["options"]["env"]
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertNotIn("ANTHROPIC_PROFILE", env)

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
