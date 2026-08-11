# CDX Manager 0.18.1

## Fixes

### `cdx tray install` works against a published release

0.18.0 shipped a tray installer that refused every asset the release published.
Three separate causes, each of which only appeared when installing from a real
release rather than from a locally built archive.

**The archive shape was rejected.** Release assets are written with
`tar -C dir .`, so they carry a member for the directory itself. The guard that
refuses an archive escaping its install directory treated that member as an
escape, when it resolves to the destination and nothing else. The destination is
now accepted; an archive that genuinely writes outside its directory is still
refused, and a link member still is.

**Windows asked for an asset nobody builds.** CDX looked for
`x86_64-pc-windows-gnu` while releases are built with the MSVC toolchain, so no
published checksum ever matched the name it asked for. Every Windows install
refused for want of a checksum that was published under a different target.

**ARM Linux was offered and never built.** `aarch64-unknown-linux-musl` was a
target CDX would install and the release did not produce. It is now built and
published alongside the others.

A test now asserts that every target CDX offers is one the release actually
builds, so this class of mismatch fails in CI rather than on a user's machine.

### Windows toasts carry the CDX icon

The Start Menu shortcut CDX installs now points at an icon shipped with the
companion, so a notification shows the CDX logo rather than a generic one.
Uninstall removes the shortcut along with the companion.

## Release safety

Publishing to npm and PyPI now waits for the tray companion assets to build
successfully. All four workflows fire on the same release event, so previously
they ran beside each other: a failed asset build would have left both registries
carrying a version whose release had no companion to install.

## Validation

- `npm run lint`
- `npm test` — 771 Python tests
- `cargo test` — 45 Rust tests; `cargo clippy` clean with zero warnings on three
  targets
- `cdx tray install`, `doctor`, `launch` and `uninstall` exercised against the
  published v0.18.0 assets on macOS arm64, Windows, and Linux under WSL
