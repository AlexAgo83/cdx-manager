# Tray companion

The system tray companion lives in its own repository,
[cdx-tray](https://github.com/AlexAgo83/cdx-tray): its sources, local testing loops, signing and
releases are documented there.

CDX's side of the contract is `cdx tray status --json` (`src/tray_contract.py`). Its `schema`
major is the breaking-change marker: `test/test_tray_contract_shape_py.py` pins the JSON shape per
version, a minor may only add keys, and a major bump needs a cdx-tray release that reads it.
`cdx tray install` installs the newest cdx-tray release recorded for this CDX's major, verified
against the cdx-tray checksum ledger; CDX versions released before the split keep their own tray
assets.
