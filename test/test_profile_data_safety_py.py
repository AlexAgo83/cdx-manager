import base64
import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import claude_credentials, claude_usage, session_backup, session_service
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
            mock.patch.object(session_service, "_link_macos_keychain"),
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
    def test_copy_never_reads_external_keychain_and_copies_only_profile_entry(self):
        source = self.profile("source")
        source_service = self.credential(source, "source-token")
        external = self.base / "fake-keychains"
        external.mkdir()
        (external / "login.keychain-db").write_text("external sentinel")
        library = Path(source["authHome"]) / "Library"
        library.mkdir()
        (library / "Keychains").symlink_to(external, target_is_directory=True)
        self.entries["Claude Code-credentials"] = {"global": "untouched"}
        real_copy = session_service.shutil.copy2

        def guarded_copy(src, dest, **kwargs):
            self.assertNotIn("Keychains", str(src))
            return real_copy(src, dest, **kwargs)

        real_tree = session_service.shutil.copytree
        def guarded_tree(*args, **kwargs):
            if len(args) < 5:
                kwargs["copy_function"] = guarded_copy
            return real_tree(*args, **kwargs)

        with mock.patch.object(session_service.shutil, "copytree", side_effect=guarded_tree):
            result = session_service.copy_session(str(self.base), self.store, "source", "copied")
        dest = result["session"]
        self.assertEqual(claude_credentials.read_keychain_credentials(dest["authHome"]), self.entries[source_service])
        self.assertFalse((Path(dest["authHome"]) / "Library" / "Keychains" / "login.keychain-db").exists())
        self.assertEqual(self.entries["Claude Code-credentials"], {"global": "untouched"})
        self.assertTrue(session_service._link_macos_keychain.called)

    def test_copy_failure_restores_existing_destination_credential_and_profile(self):
        source = self.profile("source")
        dest = self.profile("dest")
        self.credential(source, "source-token")
        self.credential(dest, "dest-token")
        before = copy.deepcopy(self.entries)
        marker = Path(dest["authHome"]) / "marker"
        marker.write_text("keep")
        with mock.patch.dict(self.store, {"replace_session": mock.Mock(side_effect=OSError("store failed"))}):
            with self.assertRaises(OSError):
                session_service.copy_session(str(self.base), self.store, "source", "dest")
        self.assertEqual(self.entries, before)
        self.assertEqual(marker.read_text(), "keep")
        self.assertEqual(self.store["get_session"]("dest"), dest)

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

    def test_export_carries_the_keychain_credential_and_import_makes_it_the_live_one(self):
        source = self.profile("keychain")
        self.credential(source, "source-token")
        bundle = self.base / "auth.cdx"
        result = session_backup.export_bundle(str(self.base), self.store, str(bundle),
                                              include_auth=True, passphrase="fake")
        self.assertTrue(result["include_auth"])
        self.assertEqual(result["profile_file_count"], 1)

        dest = self.base / "restored"
        dest.mkdir()
        store = create_session_store(str(dest))
        session_backup.import_bundle(str(dest), store, str(bundle), passphrase="fake")
        restored = store["get_session"]("keychain")
        credentials = json.loads((Path(restored["authHome"]) / ".claude" / ".credentials.json").read_text())
        self.assertEqual(credentials["claudeAiOauth"]["accessToken"], "source-token")

        # A stale entry on the destination must not shadow the imported credential.
        stale = self.credential(restored, "stale-token")
        session_backup.import_bundle(str(dest), store, str(bundle), passphrase="fake", force=True)
        self.assertNotIn(stale, self.entries)

    def test_export_prefers_the_keychain_over_a_stale_credential_file(self):
        source = self.profile("keychain")
        self.credential(source, "live-token")
        claude = Path(source["authHome"]) / ".claude"
        claude.mkdir()
        (claude / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "stale-file"}}))
        bundle = self.base / "auth.cdx"
        session_backup.export_bundle(str(self.base), self.store, str(bundle), include_auth=True, passphrase="fake")
        dest = self.base / "restored"
        dest.mkdir()
        store = create_session_store(str(dest))
        session_backup.import_bundle(str(dest), store, str(bundle), passphrase="fake")
        restored = store["get_session"]("keychain")
        credentials = json.loads((Path(restored["authHome"]) / ".claude" / ".credentials.json").read_text())
        self.assertEqual(credentials["claudeAiOauth"]["accessToken"], "live-token")

    def test_export_failure_has_nonzero_text_and_json_cli_outcomes(self):
        from src.cli import cli_entry

        source = self.profile("keychain")
        self.credential(source, "synthetic-secret")
        output = self.base / "existing.cdx"
        output.write_bytes(b"keep previous backup")
        denied = SimpleNamespace(returncode=36, stdout="synthetic-secret", stderr="synthetic-secret")
        for json_mode in (False, True):
            stderr, stdout = io.StringIO(), io.StringIO()
            argv = ["cdx", "export", str(output), "--force", "--include-auth", "--passphrase-env", "CDX_TEST_PASSPHRASE"]
            if json_mode:
                argv.append("--json")
            with self.subTest(json_mode=json_mode), mock.patch.object(claude_credentials, "_security", return_value=denied), \
                    mock.patch("sys.argv", argv), mock.patch("sys.stderr", stderr), mock.patch("sys.stdout", stdout), \
                    mock.patch.dict(os.environ, {"CDX_HOME": str(self.base), "CDX_TEST_PASSPHRASE": "fake-passphrase"}):
                with self.assertRaises(SystemExit) as error:
                    cli_entry()
                self.assertNotEqual(error.exception.code, 0)
            diagnostic = stderr.getvalue()
            self.assertIn("keychain", diagnostic)
            self.assertNotIn("synthetic-secret", diagnostic + stdout.getvalue())
            if json_mode:
                self.assertFalse(json.loads(diagnostic)["ok"])
            self.assertEqual(output.read_bytes(), b"keep previous backup")

    def test_export_denied_keychain_never_replaces_output(self):
        self.profile("keychain")
        output = self.base / "existing.cdx"
        output.write_bytes(b"keep")
        denied = SimpleNamespace(returncode=36, stdout="synthetic-secret", stderr="synthetic-secret")
        with mock.patch.object(claude_credentials, "_security", return_value=denied):
            with self.assertRaisesRegex(CdxError, "Cannot export authentication for keychain"):
                session_backup.export_bundle(str(self.base), self.store, str(output), include_auth=True, force=True, passphrase="fake")
        self.assertEqual(output.read_bytes(), b"keep")

    def test_rename_moves_only_profile_authentication(self):
        source = self.profile("source")
        old_service = self.credential(source, "source-token")
        other = self.profile("other")
        other_service = self.credential(other, "other-token")
        renamed = session_service.rename_session(str(self.base), self.store, "source", "renamed")
        self.assertNotIn(old_service, self.entries)
        self.assertEqual(claude_credentials.read_keychain_credentials(renamed["authHome"])["claudeAiOauth"]["accessToken"], "source-token")
        self.assertEqual(self.entries[other_service]["claudeAiOauth"]["accessToken"], "other-token")
        self.assertIsNone(self.store["get_session"]("source"))

    def test_rename_store_failure_and_collision_preserve_original(self):
        source = self.profile("source")
        self.credential(source, "source-token")
        before = copy.deepcopy(self.entries)
        with mock.patch.dict(self.store, {"rename_session": mock.Mock(side_effect=OSError("store failed"))}):
            with self.assertRaises(OSError):
                session_service.rename_session(str(self.base), self.store, "source", "renamed")
        self.assertEqual(self.entries, before)
        self.assertTrue(Path(source["authHome"]).is_dir())
        self.assertEqual(self.store["get_session"]("source"), source)
        dest_home = str(self.base / "profiles" / "renamed" / "claude-home")
        self.entries[claude_credentials._keychain_identity(dest_home)[1]] = {"unrelated": "preserve"}
        with self.assertRaisesRegex(CdxError, "refusing to overwrite"):
            session_service.rename_session(str(self.base), self.store, "source", "renamed")
        self.assertEqual(self.store["get_session"]("source"), source)

    def test_rename_cleanup_failure_keeps_working_destination(self):
        source = self.profile("source")
        old_service = self.credential(source, "source-token")
        with mock.patch.object(session_service, "delete_keychain_credentials", side_effect=CdxError("denied")):
            with self.assertRaisesRegex(CdxError, "new session is usable"):
                session_service.rename_session(str(self.base), self.store, "source", "renamed")
        self.assertIn(old_service, self.entries)
        renamed = self.store["get_session"]("renamed")
        self.assertTrue(Path(renamed["authHome"]).is_dir())
        self.assertEqual(claude_credentials.read_keychain_credentials(renamed["authHome"]), self.entries[old_service])

    def test_rename_write_verification_and_directory_failures_preserve_source(self):
        source = self.profile("source")
        self.credential(source, "source-token")
        before = copy.deepcopy(self.entries)
        real_security = self.security

        def deny_or_drop_write(args, *, input_text=None):
            if args == ["-i"]:
                return SimpleNamespace(returncode=0, stdout="", stderr="write was refused")
            return real_security(args, input_text=input_text)

        with mock.patch.object(claude_credentials, "_security", side_effect=deny_or_drop_write):
            with self.assertRaisesRegex(CdxError, "verification failed"):
                session_service.rename_session(str(self.base), self.store, "source", "renamed")
        self.assertEqual(self.entries, before)
        self.assertEqual(self.store["get_session"]("source"), source)
        with mock.patch.object(session_service.os, "rename", side_effect=OSError("move failed")):
            with self.assertRaises(OSError):
                session_service.rename_session(str(self.base), self.store, "source", "renamed")
        self.assertEqual(self.entries, before)
        self.assertTrue(Path(source["authHome"]).is_dir())

    @unittest.skipIf(os.name == "nt", "POSIX account database used by native macOS runner")
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


    def test_remove_deletes_the_profile_credential_and_frees_the_name(self):
        gone = self.profile("gone")
        kept = self.profile("kept")
        gone_service = self.credential(gone, "gone-token")
        kept_service = self.credential(kept, "kept-token")
        session_service.remove_session(str(self.base), self.store, "gone")
        self.assertNotIn(gone_service, self.entries)
        self.assertIn(kept_service, self.entries)
        # The freed name must be reusable: a stale entry would refuse the copy.
        result = session_service.copy_session(str(self.base), self.store, "kept", "gone")
        self.assertEqual(claude_credentials.read_keychain_credentials(result["session"]["authHome"]),
                         self.entries[kept_service])

    def test_remove_reports_a_credential_that_could_not_be_deleted(self):
        record = self.profile("gone")
        self.credential(record, "gone-token")
        with mock.patch.object(claude_credentials, "_security", return_value=SimpleNamespace(returncode=1, stdout="", stderr="")):
            with self.assertRaises(CdxError) as error:
                session_service.remove_session(str(self.base), self.store, "gone")
        self.assertIn("Removed session gone", str(error.exception))
        self.assertIsNone(self.store["get_session"]("gone"))

    def test_copy_over_a_claude_destination_from_another_provider_leaves_no_credential(self):
        self.profile("codex-src", "codex")
        dest = self.profile("claude-dest")
        dest_service = self.credential(dest, "dest-token")
        session_service.copy_session(str(self.base), self.store, "codex-src", "claude-dest")
        self.assertNotIn(dest_service, self.entries)
        self.assertEqual(self.store["get_session"]("claude-dest")["provider"], "codex")

    def test_an_unusable_keychain_falls_back_to_credential_files(self):
        from src.provider_runtime import _read_claude_launch_oauth_token

        record = self.profile("locked")
        home = Path(record["authHome"])
        (home / ".claude").mkdir()
        (home / ".claude" / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "file-token"}}))
        locked = SimpleNamespace(returncode=36, stdout="", stderr="keychain is locked")
        with mock.patch.object(claude_credentials, "_security", return_value=locked):
            with mock.patch.object(claude_usage, "fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 40}) as probe:
                result = claude_usage.refresh_claude_session_status(record, auth_refresher=lambda _: None)
            probe.assert_called_once_with("file-token")
            self.assertEqual(result["remaining_5h_pct"], 40)
            # Launching must not die on a keychain it cannot read either.
            (home / "credentials").mkdir()
            (home / "credentials" / "default.json").write_text(json.dumps({"access_token": "launch-token"}))
            (home / ".claude" / ".credentials.json").unlink()
            self.assertEqual(_read_claude_launch_oauth_token(str(home)), "launch-token")

    def test_a_custom_oauth_endpoint_blocks_writes_but_still_allows_reads(self):
        source = self.profile("source")
        self.credential(source, "source-token")
        with mock.patch.dict(os.environ, {"USE_LOCAL_OAUTH": "1"}):
            self.assertIsNotNone(claude_credentials.read_keychain_credentials(source["authHome"]))
            with self.assertRaises(CdxError):
                claude_credentials.write_keychain_credentials(source["authHome"], {"a": 1})
            with self.assertRaises(CdxError):
                claude_credentials.delete_keychain_credentials(source["authHome"])


if __name__ == "__main__":
    unittest.main()
