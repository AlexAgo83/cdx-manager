import os
import tempfile
import unittest

from src.context_store import (
    clear_context,
    edit_context,
    get_context_path,
    init_context,
    install_context_for_session,
    read_context,
    write_context,
)
from src.errors import CdxError


class ContextStorePythonTests(unittest.TestCase):
    def test_init_read_write_and_clear_context(self):
        with tempfile.TemporaryDirectory(prefix="cdx-context-") as temp_dir:
            workspace = os.path.join(temp_dir, "workspace")
            os.makedirs(workspace, exist_ok=True)

            initialized = init_context(temp_dir, cwd=workspace)
            self.assertTrue(initialized["created"])
            self.assertIn("# Shared Context", read_context(temp_dir, cwd=workspace))

            existing = init_context(temp_dir, cwd=workspace)
            self.assertFalse(existing["created"])

            written = write_context(temp_dir, "Goal: ship\n\n", cwd=workspace)
            self.assertEqual(read_context(temp_dir, cwd=workspace), "Goal: ship\n")
            self.assertEqual(written["bytes"], os.path.getsize(get_context_path(temp_dir, cwd=workspace)))

            self.assertTrue(clear_context(temp_dir, cwd=workspace)["removed"])
            self.assertFalse(clear_context(temp_dir, cwd=workspace)["removed"])

    def test_edit_context_requires_editor_and_invokes_custom_spawn(self):
        with tempfile.TemporaryDirectory(prefix="cdx-context-") as temp_dir:
            calls = []

            def spawn(command, args, options):
                calls.append((command, args, options))
                return {"returncode": 0}

            with self.assertRaisesRegex(CdxError, "VISUAL or EDITOR"):
                edit_context(temp_dir, env={"PATH": ""})

            result = edit_context(
                temp_dir,
                editor="code --wait",
                env={"EDITOR": "unused"},
                spawn_sync=spawn,
            )

        self.assertTrue(result["edited"])
        self.assertEqual(calls[0][0], "code")
        self.assertEqual(calls[0][1][0], "--wait")
        self.assertTrue(calls[0][1][1].endswith("context.md"))

    def test_install_context_for_session_writes_shared_context(self):
        with tempfile.TemporaryDirectory(prefix="cdx-context-") as temp_dir:
            workspace = os.path.join(temp_dir, "workspace")
            auth_home = os.path.join(temp_dir, "profile")
            write_context(temp_dir, "Use the cached plan.", cwd=workspace)

            result = install_context_for_session(
                temp_dir,
                {"name": "work", "authHome": auth_home},
                cwd=workspace,
            )

            self.assertTrue(result["target_path"].endswith("shared-context.md"))
            with open(result["target_path"], encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "Use the cached plan.\n")

    def test_install_context_rejects_missing_context_or_auth_home(self):
        with tempfile.TemporaryDirectory(prefix="cdx-context-") as temp_dir:
            with self.assertRaisesRegex(CdxError, "No shared context"):
                install_context_for_session(temp_dir, {"name": "work", "authHome": temp_dir})

            write_context(temp_dir, "Context")
            with self.assertRaisesRegex(CdxError, "auth home missing"):
                install_context_for_session(temp_dir, {"name": "work"})

    def test_context_path_is_stable_per_workspace(self):
        with tempfile.TemporaryDirectory(prefix="cdx-context-") as temp_dir:
            first = get_context_path(temp_dir, cwd=os.path.join(temp_dir, "a"))
            second = get_context_path(temp_dir, cwd=os.path.join(temp_dir, "a"))
            third = get_context_path(temp_dir, cwd=os.path.join(temp_dir, "b"))

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)


if __name__ == "__main__":
    unittest.main()


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_write_replaces_content_and_leaves_no_temp_files(self):
        from src.fs_utils import atomic_write

        with tempfile.TemporaryDirectory(prefix="cdx-atomic-") as temp_dir:
            path = os.path.join(temp_dir, "target.md")
            atomic_write(path, "first\n")
            atomic_write(path, "second\n", mode=0o600)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "second\n")
            if os.name != "nt":
                self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o600")
            self.assertEqual(os.listdir(temp_dir), ["target.md"])

    def test_atomic_write_failure_keeps_previous_content(self):
        from src.fs_utils import atomic_write

        with tempfile.TemporaryDirectory(prefix="cdx-atomic-") as temp_dir:
            path = os.path.join(temp_dir, "target.md")
            atomic_write(path, "kept\n")
            with self.assertRaises(TypeError):
                atomic_write(path, 12345)  # not str/bytes: the write fails mid-flight
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "kept\n")
            self.assertEqual(os.listdir(temp_dir), ["target.md"])
