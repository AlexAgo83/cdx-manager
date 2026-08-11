# CDX Manager 0.18.2

## Fixes

### `cdx tray install` can install the companion for the release you are running

No release could ever install its own tray companion, and the cause was
structural rather than a bug. Tray assets are built after the tag exists, so
their checksums are recorded afterwards — which means a package built at tag
time ships a checksum ledger that stops at the previous release. Installing
refused with "No published checksum for … of CDX <this version>".

The release already publishes `release-archives.json` beside the assets. A
missing local entry now falls through to it.

What that is worth, stated plainly: it is the publisher's own assertion fetched
over the same HTTPS channel as the asset, so it does not defend against someone
able to rewrite the release. It does defend against a truncated download and an
asset built for another architecture, which are the failures that happen. A
checksum committed to the repository before the asset existed is the stronger
claim, so a local entry always wins and fetches nothing.

### The PyPI package can start

`pyproject.toml` declared only the root package, so `cdx_manager.commands` was
absent from every wheel since it was extracted and `pip install cdx-manager`
produced a CLI that failed at import. setuptools does not warn about a
subpackage it was never told about: the wheel builds cleanly and breaks on the
user's machine.

The npm package and the standalone installer were unaffected — both ship the
source tree wholesale.

A test now asserts every package under `src/` is declared for the wheel.

## Validation

- `npm run lint`
- `npm test` — 775 Python tests
- A wheel built from this tree installs into a clean virtualenv and runs
  `cdx --version` and `cdx tray doctor`
- `cdx tray install` exercised against a checksum ledger with no entry for the
  version, which is the shape every shipped package has
