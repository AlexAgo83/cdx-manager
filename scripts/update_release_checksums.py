#!/usr/bin/env python3

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path


DEFAULT_REPO = "AlexAgo83/cdx-manager"


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url, dest_path):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "cdx-manager-release-checksum-updater",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        with open(dest_path, "wb") as handle:
            handle.write(response.read())


def _archive_urls(repo, tag):
    return {
        "github_tarball_sha256": f"https://github.com/{repo}/archive/refs/tags/{tag}.tar.gz",
        "github_zip_sha256": f"https://github.com/{repo}/archive/refs/tags/{tag}.zip",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download a published GitHub release archive and update checksums/release-archives.json."
    )
    parser.add_argument("--tag", required=True, help="Release tag, for example v0.4.0")
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repository in owner/name form (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--checksums-file",
        default="checksums/release-archives.json",
        help="Path to the release checksums JSON file",
    )
    args = parser.parse_args(argv)

    checksums_path = Path(args.checksums_file)
    if not checksums_path.exists():
        raise SystemExit(f"Checksums file not found: {checksums_path}")

    payload = json.loads(checksums_path.read_text(encoding="utf-8"))
    releases = payload.setdefault("releases", {})
    release_entry = releases.setdefault(args.tag, {})

    with tempfile.TemporaryDirectory(prefix="cdx-release-checksums-") as temp_dir:
        temp_root = Path(temp_dir)
        for field, url in _archive_urls(args.repo, args.tag).items():
            archive_path = temp_root / field
            print(f"Downloading {url}", file=sys.stderr)
            _download(url, archive_path)
            checksum = _sha256_file(archive_path)
            release_entry[field] = checksum
            print(f"{field}={checksum}", file=sys.stderr)

    checksums_path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    print(f"Updated {checksums_path} for {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
