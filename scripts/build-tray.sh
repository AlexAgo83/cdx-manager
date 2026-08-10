#!/usr/bin/env bash
# Build the CDX tray companion, and on macOS wrap and sign it as CDX.app.
#
# adr_005 settles the signing story this implements:
#   - Apple Silicon refuses to execute unsigned arm64 code, so signing is a
#     build step, not a distribution option.
#   - The identity is a self-signed certificate on the build machine. Ad-hoc is
#     explicitly rejected: it mints a new identity every build, so macOS forgets
#     the notification grant at each companion update.
#   - Gatekeeper never sees the result, because `cdx tray install` fetches the
#     asset and no quarantine attribute is applied. That is why no Developer ID
#     is needed, and why a browser download link must never be offered.
#
# Create the identity once, in Keychain Access: Certificate Assistant ->
# Create a Certificate -> Self Signed Root, Code Signing. Then export and back
# it up outside this repository: losing it changes the app's identity and every
# user has to re-authorize notifications.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRATE_DIR="$REPO_ROOT/tray"
BUNDLE_ID="${CDX_TRAY_BUNDLE_ID:-com.cdx.tray}"
APP_NAME="CDX.app"

die() { printf 'build-tray: %s\n' "$1" >&2; exit 1; }

# --dev builds a bundle you can launch locally without a certificate. It is not
# distributable: the linker's ad-hoc signature changes every build, so macOS
# forgets the notification grant each time and the tray loses its own icon in
# notifications. Never ship the output of --dev.
DEV_BUILD=0
for arg in "$@"; do [ "$arg" = "--dev" ] && DEV_BUILD=1; done

# --linux builds the Linux asset, statically linked against musl, from any host.
# Static musl is what makes the Linux asset a single file with no runtime
# prerequisite, which is the property adr_005 asked for when it chose ksni over
# tray-icon: ksni and zbus are pure Rust, so nothing here needs a C library.
#
# It links through rust-lld rather than the host `cc`, so no C toolchain is
# required to produce it — verified by building this on macOS for a WSL Ubuntu
# that has neither gcc nor libc6-dev.
LINUX_BUILD=0
for arg in "$@"; do [ "$arg" = "--linux" ] && LINUX_BUILD=1; done

# --package also writes the release asset, named exactly as `cdx tray install`
# will ask for it. The name carries the version and the target because the
# installer reads them back from it: a mislabelled file must not be recordable
# under a target it cannot run on.
PACKAGE=0
for arg in "$@"; do [ "$arg" = "--package" ] && PACKAGE=1; done

DIST_DIR="$REPO_ROOT/dist"

package_asset() {
  local target="$1" parent="$2" payload="$3"
  local asset="cdx-tray-$VERSION-$target.tar.gz"
  mkdir -p "$DIST_DIR"
  # Archived from its parent so the payload sits at the archive root, which is
  # where the installer looks. -C keeps absolute paths out of the member names.
  tar czf "$DIST_DIR/$asset" -C "$parent" "$payload"
  printf 'build-tray: packaged %s\n' "$DIST_DIR/$asset"
  printf 'build-tray: record it with: python3 scripts/record_tray_checksums.py %s\n' "$DIST_DIR/$asset"
}

command -v cargo >/dev/null 2>&1 || die "cargo not found. Install Rust: https://rustup.rs"

VERSION="$(tr -d '[:space:]' < "$REPO_ROOT/VERSION")"
[ -n "$VERSION" ] || die "VERSION is empty"

if [ "$LINUX_BUILD" = "1" ]; then
  TARGET=x86_64-unknown-linux-musl
  rustup target list --installed 2>/dev/null | grep -qx "$TARGET" \
    || die "target $TARGET is not installed. Run: rustup target add $TARGET"

  # rust-lld is a generic driver and refuses to guess which linker it is, so it
  # is reached through a wrapper that names the GNU flavour.
  RUST_LLD="$(rustc --print sysroot)/lib/rustlib/$(rustc -vV | sed -n 's/^host: //p')/bin/rust-lld"
  [ -x "$RUST_LLD" ] || die "rust-lld not found at $RUST_LLD"
  LLD_DIR="$(mktemp -d)"
  trap 'rm -rf "$LLD_DIR"' EXIT
  printf '#!/bin/sh\nexec %s -flavor gnu "$@"\n' "$RUST_LLD" > "$LLD_DIR/ld.lld"
  chmod +x "$LLD_DIR/ld.lld"

  printf 'build-tray: building cdx-tray %s for %s\n' "$VERSION" "$TARGET"
  CARGO_TARGET_X86_64_UNKNOWN_LINUX_MUSL_LINKER="$LLD_DIR/ld.lld" \
  CARGO_TARGET_X86_64_UNKNOWN_LINUX_MUSL_RUSTFLAGS="-C linker-flavor=ld -C link-self-contained=yes" \
    cargo build --release --target "$TARGET" --manifest-path "$CRATE_DIR/Cargo.toml"

  LINUX_BINARY="$CRATE_DIR/target/$TARGET/release/cdx-tray"
  [ -x "$LINUX_BINARY" ] || die "cargo did not produce $LINUX_BINARY"
  printf 'build-tray: built %s\n' "$LINUX_BINARY"
  [ "$PACKAGE" = "1" ] && package_asset "$TARGET" "$(dirname "$LINUX_BINARY")" cdx-tray
  exit 0
fi

printf 'build-tray: building cdx-tray %s\n' "$VERSION"
cargo build --release --manifest-path "$CRATE_DIR/Cargo.toml"
BINARY="$CRATE_DIR/target/release/cdx-tray"
[ -x "$BINARY" ] || die "cargo did not produce $BINARY"

if [ "$(uname -s)" != "Darwin" ]; then
  printf 'build-tray: built %s\n' "$BINARY"
  if [ "$PACKAGE" = "1" ]; then
    NATIVE_TARGET="$(rustc -vV | sed -n 's/^host: //p')"
    package_asset "$NATIVE_TARGET" "$(dirname "$BINARY")" "$(basename "$BINARY")"
  fi
  exit 0
fi

# LSUIElement keeps the companion out of the Dock and the app switcher: it owns
# a menu bar item, not a window. The bundle identifier must stay stable, because
# the notification grant is bound to it together with the signature.
APP_DIR="$CRATE_DIR/target/release/$APP_NAME"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$BINARY" "$APP_DIR/Contents/MacOS/cdx-tray"
# The menu bar glyphs are compiled into the binary; this icon is what Finder,
# Login Items and the notification banner show for the app itself.
cp "$CRATE_DIR/assets/icons/CDX.icns" "$APP_DIR/Contents/Resources/CDX.icns"
cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>CDX</string>
	<key>CFBundleDisplayName</key><string>CDX</string>
	<key>CFBundleExecutable</key><string>cdx-tray</string>
	<key>CFBundleIconFile</key><string>CDX</string>
	<key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleShortVersionString</key><string>$VERSION</string>
	<key>CFBundleVersion</key><string>$VERSION</string>
	<key>LSMinimumSystemVersion</key><string>11.0</string>
	<key>LSUIElement</key><true/>
	<key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
plutil -lint "$APP_DIR/Contents/Info.plist" >/dev/null || die "generated Info.plist is malformed"

if [ "$DEV_BUILD" = "1" ]; then
  # Refused rather than ignored: a dev bundle that got packaged would be
  # indistinguishable from a release asset once it had a checksum recorded, and
  # its identity changes every build.
  [ "$PACKAGE" = "1" ] && die "--dev cannot be packaged: its signature changes every build, so an asset built this way would reset the notification grant at every update. See adr_005."
  printf 'build-tray: DEV BUILD, not signed with a stable identity.\n' >&2
  printf 'build-tray: launchable locally, NOT distributable. Notification\n' >&2
  printf 'build-tray: permission will reset on every rebuild. See adr_005.\n' >&2
  printf 'build-tray: built %s\n' "$APP_DIR"
  exit 0
fi

IDENTITY="${CDX_TRAY_SIGN_IDENTITY:-}"
if [ -z "$IDENTITY" ]; then
  die "CDX_TRAY_SIGN_IDENTITY is unset.

Set it to the name of a self-signed code-signing certificate in your keychain.
Ad-hoc signing (-s -) is deliberately not used as a fallback: its identity
changes every build, so macOS drops the notification grant at each update and
the tray loses its own icon in notifications. See adr_005.

  security find-identity -v -p codesigning    # list what you have
  CDX_TRAY_SIGN_IDENTITY='CDX Build' $0       # then re-run"
fi

printf 'build-tray: signing %s as %s\n' "$APP_NAME" "$IDENTITY"
codesign --force --sign "$IDENTITY" --timestamp=none --options runtime "$APP_DIR"
codesign --verify --deep --strict "$APP_DIR" || die "signature did not verify"

printf 'build-tray: built and signed %s\n' "$APP_DIR"
printf 'build-tray: bundle id %s, version %s\n' "$BUNDLE_ID" "$VERSION"

# Packaged only after the signature verified. An asset is what a user ends up
# executing, so shipping one that failed verification would defeat the whole
# checksum-vouches-for-a-self-signed-binary story adr_005 rests on.
if [ "$PACKAGE" = "1" ]; then
  package_asset "$(rustc -vV | sed -n 's/^host: //p')" "$(dirname "$APP_DIR")" "$APP_NAME"
fi
