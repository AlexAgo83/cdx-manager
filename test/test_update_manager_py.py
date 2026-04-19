import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from src.update_manager import build_update_plan, detect_installation
from src.errors import CdxError


class UpdateManagerPythonTests(unittest.TestCase):
    def make_temp_dir(self):
        return tempfile.mkdtemp(prefix="cdx-update-py-")

    def test_detect_installation_modes(self):
        root = self.make_temp_dir()
        with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        self.assertEqual(detect_installation(package_root=root), {"mode": "npm", "package_root": os.path.realpath(root)})

        source_root = self.make_temp_dir()
        os.makedirs(os.path.join(source_root, ".git"), exist_ok=True)
        self.assertEqual(detect_installation(package_root=source_root), {"mode": "source", "package_root": os.path.realpath(source_root)})

        venv_root = self.make_temp_dir()
        self.assertEqual(
            detect_installation(package_root=venv_root, prefix="/tmp/fake-venv", base_prefix="/usr"),
            {"mode": "python", "package_root": os.path.realpath(venv_root)},
        )

        standalone_root = os.path.join(self.make_temp_dir(), "versions", "1.2.3")
        os.makedirs(standalone_root, exist_ok=True)
        self.assertEqual(
            detect_installation(package_root=standalone_root),
            {"mode": "standalone", "package_root": os.path.realpath(standalone_root)},
        )

    def test_standalone_plan_uses_local_installer(self):
        standalone_root = os.path.join(self.make_temp_dir(), "versions", "1.2.3")
        os.makedirs(standalone_root, exist_ok=True)

        with mock.patch("src.update_manager.sys.platform", "linux"):
            plan = build_update_plan(target_version="v1.4.0", package_root=standalone_root)

        self.assertEqual(plan["mode"], "standalone")
        self.assertEqual(plan["target_version"], "1.4.0")
        self.assertEqual(plan["steps"][0]["command"][0], "sh")
        self.assertEqual(plan["steps"][0]["env"]["CDX_VERSION"], "1.4.0")

    def test_source_checkout_refuses_dirty_tree(self):
        source_root = self.make_temp_dir()
        os.makedirs(os.path.join(source_root, ".git"), exist_ok=True)

        with mock.patch("src.update_manager.subprocess.run", return_value=SimpleNamespace(stdout=" M src/cli.py\n", returncode=0)):
            with self.assertRaisesRegex(CdxError, "uncommitted changes"):
                build_update_plan(package_root=source_root)
