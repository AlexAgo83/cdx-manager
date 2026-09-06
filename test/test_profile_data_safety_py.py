import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import claude_credentials, claude_usage, session_backup
from src.backup_bundle import encode_bundle
from src.errors import CdxError
from src.session_store import create_session_store

_REAL_SECURITY = claude_credentials._security


class ProfileDataSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cdx-profile-safety-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.store = create_session_store(str(self.base))
        self.entries = {}
        self.keychain_calls = []
        for patcher in (
            mock.patch.object(claude_credentials, "sys", SimpleNamespace(platform="darwin")),
            mock.patch.dict(os.environ, {"USER": "cdx-test", "USE_LOCAL_OAUTH": "", "CLAUDE_CODE_CUSTOM_OAUTH_URL": ""}),
            mock.patch.object(claude_credentials, "_security", side_effect=self.security),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def security(self, args, *, input_text=None):
        import shlex

        self.keychain_calls.append((list(args), input_text))
        command = shlex.split(input_text) if args == ["-i"] else args
        service = command[command.index("-s") + 1]
        if command[0] == "find-generic-password":
            if service not in self.entries:
                return SimpleNamespace(returncode=44, stdout="", stderr="not found")
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.entries[service]), stderr="")
        if command[0] == "add-generic-password":
            self.entries[service] = json.loads(bytes.fromhex(command[command.index("-X") + 1]))
        elif command[0] == "delete-generic-password":
            self.entries.pop(service, None)
        else:
            raise AssertionError(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def profile(self, name, provider="claude"):
        root = self.base / "profiles" / name
        home = root / "claude-home" if provider == "claude" else root
        home.mkdir(parents=True)
        record = {"name": name, "provider": provider, "sessionRoot": str(root), "authHome": str(home)}
        self.store["add_session"](record)
        return record

    def credential(self, record, token):
        service = claude_credentials._keychain_identity(record["authHome"])[1]
        self.entries[service] = {"claudeAiOauth": {"accessToken": token, "refreshToken": "fake-refresh"}}
        return service

    def bundle(self, name, files, state=None):
        path = self.base / "bundle.cdx"
        payload = {"schema_version": 1, "sessions": [{"name": name, "provider": "codex"}],
                   "profiles": {name: [{"path": p, "data_b64": base64.b64encode(value.encode()).decode()} for p, value in files]},
                   "states": {name: state or {}}}
        path.write_bytes(encode_bundle(payload))
        return str(path)

    def test_merge_failure_preserves_original_files_record_and_state(self):
        record = self.profile("merge", "codex")
        root = Path(record["sessionRoot"])
        (root / "auth.json").write_text("original")
        state = {"status": "running", "local": "preserve"}
        self.store["write_session_state"]("merge", state)
        bundle = self.bundle("merge", [("added/one", "new"), ("added/two", "fail")])
        real_write = session_backup.atomic_write

        def fail(path, data, **kwargs):
            if str(path).endswith("two"):
                raise OSError("write failed")
            return real_write(path, data, **kwargs)

        with mock.patch.object(session_backup, "atomic_write", side_effect=fail):
            with self.assertRaises(OSError):
                session_backup.import_bundle(str(self.base), self.store, bundle, merge=True)
        self.assertEqual((root / "auth.json").read_text(), "original")
        self.assertFalse((root / "added").exists())
        self.assertEqual(self.store["get_session"]("merge"), record)
        self.assertEqual(self.store["read_session_state"]("merge"), state)

    def test_merge_state_failure_restores_state_and_failed_recovery_keeps_snapshot(self):
        record = self.profile("merge", "codex")
        root = Path(record["sessionRoot"])
        (root / "auth.json").write_text("original")
        state = {"status": "running"}
        self.store["write_session_state"]("merge", state)
        bundle = self.bundle("merge", [], {"imported": True})
        real_write = self.store["write_session_state"]
        def fail_imported_state(name, value):
            if value != state:
                raise OSError("fail")
            return real_write(name, value)

        with mock.patch.dict(self.store, {"write_session_state": fail_imported_state}):
            with self.assertRaises(OSError):
                session_backup.import_bundle(str(self.base), self.store, bundle, merge=True)
        self.assertEqual(self.store["read_session_state"]("merge"), state)
        with mock.patch.dict(self.store, {"write_session_state": mock.Mock(side_effect=OSError("offline"))}):
            with self.assertRaisesRegex(CdxError, "recovery is incomplete"):
                session_backup.import_bundle(str(self.base), self.store, bundle, merge=True)
        checkpoints = list((self.base / "profiles").glob(".merge.import.*/recovery.json"))
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(json.loads(checkpoints[0].read_text()), {"session": record, "state": state})
        self.assertEqual((root / "auth.json").read_text(), "original")

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows privileges")
    def test_keychain_quota_precedence_and_launch_token_isolation(self):
        from src.provider_runtime import _read_claude_launch_oauth_token

        source = self.profile("source")
        other = self.profile("other")
        self.credential(source, "source-token")
        self.credential(other, "other-token")
        home = Path(source["authHome"])
        (home / "credentials").mkdir()
        (home / "credentials" / "default.json").write_text(json.dumps({"access_token": "stale-setup"}))
        self.assertIsNone(_read_claude_launch_oauth_token(str(home)))
        (home / ".claude").mkdir()
        (home / ".claude" / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "stale-file"}}))
        with mock.patch.object(claude_usage, "fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 70}) as probe:
            result = claude_usage.refresh_claude_session_status(source, auth_refresher=lambda _: None)
        probe.assert_called_once_with("source-token")
        self.assertEqual(result["remaining_5h_pct"], 70)

    def test_keychain_errors_are_not_missing_and_never_leak_tokens(self):
        source = self.profile("source")
        for result in [SimpleNamespace(returncode=36, stdout="secret", stderr="secret"),
                       SimpleNamespace(returncode=1, stdout="secret", stderr="secret"),
                       SimpleNamespace(returncode=0, stdout="secret", stderr=""),
                       SimpleNamespace(returncode=0, stdout="[]", stderr="")]:
            with self.subTest(result=result), mock.patch.object(claude_credentials, "_security", return_value=result):
                with self.assertRaises(CdxError) as error:
                    claude_usage.refresh_claude_session_status(source, auth_refresher=lambda _: None)
                self.assertNotIn("secret", str(error.exception))
        self.assertIsNone(claude_credentials.read_keychain_credentials(source["authHome"]))

    def test_native_runner_bounds_time_and_suppresses_provider_output(self):
        import pwd

        command = ["find-generic-password", "-a", "cdx-test", "-s", "synthetic-service", "-w"]
        with mock.patch.object(claude_credentials.subprocess, "run", return_value=SimpleNamespace(returncode=44)) as run:
            _REAL_SECURITY(command)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["timeout"], claude_credentials.KEYCHAIN_TIMEOUT_SECONDS)
        self.assertEqual(kwargs["env"]["HOME"], pwd.getpwuid(os.getuid()).pw_dir)
        for failure in [subprocess.TimeoutExpired(command, 5, output="synthetic-secret"), OSError("synthetic-secret")]:
            with mock.patch.object(claude_credentials.subprocess, "run", side_effect=failure):
                with self.assertRaises(CdxError) as error:
                    _REAL_SECURITY(command)
                self.assertNotIn("synthetic-secret", str(error.exception))

    def test_namespace_normalizes_unicode_and_rejects_hash_collisions(self):
        decomposed = str(self.base / "e\u0301")
        composed = str(self.base / "\u00e9")
        self.assertEqual(claude_credentials._keychain_identity(decomposed), claude_credentials._keychain_identity(composed))
        with mock.patch.object(claude_credentials, "_keychain_identity", return_value=("cdx-test", "same-key")):
            with self.assertRaisesRegex(CdxError, "identities collide"):
                with claude_credentials.copy_keychain_credentials("source", "dest"):
                    self.fail("Must refuse before mutation")

    def test_writes_keep_credentials_out_of_process_arguments_and_verify_readback(self):
        source = self.profile("source")
        data = {"claudeAiOauth": {"accessToken": "synthetic-secret"}}
        claude_credentials.write_keychain_credentials(source["authHome"], data)
        args, stdin = self.keychain_calls[0]
        self.assertEqual(args, ["-i"])
        self.assertNotIn("synthetic-secret", " ".join(args))
        self.assertIn("-X", stdin)
        with mock.patch.object(claude_credentials, "read_keychain_credentials", return_value=None):
            with self.assertRaisesRegex(CdxError, "verification failed"):
                claude_credentials.write_keychain_credentials(source["authHome"], data)

    def test_other_platforms_do_not_call_security(self):
        with mock.patch.object(claude_credentials, "sys", SimpleNamespace(platform="win32")):
            self.assertIsNone(claude_credentials.read_keychain_credentials("unused"))
            with claude_credentials.copy_keychain_credentials("source", "dest") as copied:
                self.assertFalse(copied)
        self.assertFalse(self.keychain_calls)


if __name__ == "__main__":
    unittest.main()
