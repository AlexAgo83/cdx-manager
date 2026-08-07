import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_release_checksums import validate_release_checksums  # noqa: E402


class ReleaseChecksumsTests(unittest.TestCase):
    def _write_release_root(self, temp_dir, version="1.2.3", releases=None):
        root = Path(temp_dir)
        (root / "src").mkdir()
        (root / "checksums").mkdir()
        (root / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        (root / "pyproject.toml").write_text(f'version = "{version}"\n', encoding="utf-8")
        (root / "src" / "cli.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
        (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (root / "checksums" / "release-archives.json").write_text(
            json.dumps({"schema_version": 1, "releases": releases or {}}),
            encoding="utf-8",
        )
        return root

    def test_release_archive_checksums_are_sha256_hex_strings(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / "checksums" / "release-archives.json").read_text(encoding="utf-8"))
        checksum_re = re.compile(r"^[0-9a-f]{64}$")

        for tag, entry in (payload.get("releases") or {}).items():
            with self.subTest(tag=tag):
                self.assertRegex(entry.get("github_tarball_sha256", ""), checksum_re)
                self.assertRegex(entry.get("github_zip_sha256", ""), checksum_re)

    def test_standalone_installers_use_tagged_release_checksum_asset(self):
        root = Path(__file__).resolve().parents[1]
        shell = (root / "install.sh").read_text(encoding="utf-8")
        powershell = (root / "install.ps1").read_text(encoding="utf-8")

        for text in (shell, powershell):
            self.assertIn("releases/download/", text)
            self.assertIn("release-archives.json", text)
            self.assertNotIn("contents/checksums/release-archives.json?ref=main", text)
            self.assertNotIn("raw.githubusercontent.com/$REPO/main/checksums/release-archives.json", text)
            self.assertIn("CDX_ALLOW_UNVERIFIED=1 disables archive integrity checks", text)

    def test_publish_workflows_use_tagged_release_checksum_asset(self):
        root = Path(__file__).resolve().parents[1]
        workflows = [
            root / ".github" / "workflows" / "publish-npm.yml",
            root / ".github" / "workflows" / "publish-pypi.yml",
        ]

        for path in workflows:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("releases/download/${RELEASE_TAG}/release-archives.json", text)
                self.assertNotIn("raw.githubusercontent.com/${GITHUB_REPOSITORY}/main/checksums", text)
                self.assertNotIn("contents/checksums/release-archives.json?ref=main", text)

    def test_release_checksum_asset_upload_workflow_is_wired(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / ".github" / "workflows" / "upload-release-checksums.yml").read_text(encoding="utf-8")

        self.assertIn("release:", text)
        self.assertIn("types:", text)
        self.assertIn("- published", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: write", text)
        self.assertIn("RELEASE_TAG:", text)
        self.assertIn("github.event.release.tag_name", text)
        self.assertIn("ref: ${{ env.RELEASE_TAG }}", text)
        self.assertIn('scripts/update_release_checksums.py --tag "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY"', text)
        self.assertIn('gh release upload "$RELEASE_TAG" checksums/release-archives.json --clobber', text)
        self.assertNotIn("secrets.", text)

    def test_windows_installer_launcher_uses_version_directory(self):
        root = Path(__file__).resolve().parents[1]
        powershell = (root / "install.ps1").read_text(encoding="utf-8")

        self.assertIn('$versionDir = $tag.TrimStart("v")', powershell)
        self.assertIn(r"set SCRIPT=%~dp0..\versions\$versionDir\bin\cdx", powershell)
        self.assertNotIn('${($tag.TrimStart("v"))}', powershell)

    def test_release_validator_reads_a_version_from_every_declaration_site(self):
        # Each source in expected_versions() must actually yield a version for
        # the real project. When cli.py stopped restating the version and began
        # resolving it, the regex scrape here silently returned "" and the
        # validator rejected every release with "Missing release version in:
        # src/cli.py" - inside the publish workflow, after the tag was already
        # public. None of the other tests in this file noticed, because they all
        # build a synthetic project whose cli.py still holds a literal.
        from verify_release_checksums import expected_versions

        versions = expected_versions(Path("."))
        empty = sorted(name for name, value in versions.items() if not value)
        self.assertEqual(empty, [], f"no version resolved from: {empty}")
        self.assertEqual(len(set(versions.values())), 1, versions)

    def test_release_validator_accepts_project_when_checksum_metadata_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(
                temp_dir,
                releases={
                    "v1.2.3": {
                        "github_tarball_sha256": "a" * 64,
                        "github_zip_sha256": "b" * 64,
                    }
                },
            )

            self.assertEqual(validate_release_checksums(root), "v1.2.3")

    def test_release_validator_rejects_a_named_tag_with_no_checksums(self):
        # An explicit tag means "validate this published release", so a missing
        # entry is a real failure. This is the path both publish workflows take.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(temp_dir)

            with self.assertRaisesRegex(ValueError, "missing release checksum metadata for v1.2.3"):
                validate_release_checksums(root, tag="v1.2.3")

    def test_release_validator_reports_an_unrecorded_version_instead_of_failing(self):
        # Without a tag the caller is asking about the working tree, whose
        # version has no entry until it is released. Failing there made the
        # command red on every checkout between releases, and a check that is
        # always red stops being read.
        from verify_release_checksums import ReleaseNotRecorded

        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(temp_dir)

            with self.assertRaises(ReleaseNotRecorded) as caught:
                validate_release_checksums(root)
            self.assertEqual(caught.exception.args[0], "v1.2.3")

    def test_release_validator_requires_both_archive_checksums(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(
                temp_dir,
                releases={
                    "v1.2.3": {
                        "github_tarball_sha256": "a" * 64,
                    }
                },
            )

            with self.assertRaisesRegex(ValueError, "github_zip_sha256"):
                validate_release_checksums(root)

    def test_release_validator_rejects_tag_version_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(temp_dir)

            with self.assertRaisesRegex(ValueError, "does not match project version"):
                validate_release_checksums(root, tag="v9.9.9")
