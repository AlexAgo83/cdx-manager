#!/usr/bin/env sh
set -eu

REPO="AlexAgo83/cdx-manager"
VERSION="${CDX_VERSION:-}"
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="${BIN_DIR:-$PREFIX/bin}"
INSTALL_ROOT="${CDX_INSTALL_ROOT:-$PREFIX/share/cdx-manager}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "cdx install: missing required command: $1" >&2
    exit 1
  fi
}

need curl
need tar
need python3

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
    return
  fi
  echo "cdx install: missing checksum tool (sha256sum or shasum)" >&2
  exit 1
}

if [ -z "$VERSION" ]; then
  VERSION="$(
    curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" |
      python3 -c 'import json, sys; print(json.load(sys.stdin)["tag_name"])'
  )"
fi

case "$VERSION" in
  v*) TAG="$VERSION" ;;
  *) TAG="v$VERSION" ;;
esac

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

ARCHIVE_URL="https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz"
curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/cdx-manager.tar.gz"

if [ -n "${CDX_SHA256:-}" ]; then
  ACTUAL_SHA256="$(sha256_file "$TMP_DIR/cdx-manager.tar.gz")"
  if [ "$ACTUAL_SHA256" != "$CDX_SHA256" ]; then
    echo "cdx install: checksum mismatch for $TAG" >&2
    echo "expected: $CDX_SHA256" >&2
    echo "actual:   $ACTUAL_SHA256" >&2
    exit 1
  fi
fi

tar -xzf "$TMP_DIR/cdx-manager.tar.gz" -C "$TMP_DIR"

SRC_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
TARGET_DIR="$INSTALL_ROOT/${TAG#v}"

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"

cp -R "$SRC_DIR"/. "$TARGET_DIR"/
chmod +x "$TARGET_DIR/bin/cdx"
ln -sfn "$TARGET_DIR/bin/cdx" "$BIN_DIR/cdx"

echo "Installed cdx $TAG to $TARGET_DIR"
echo "Linked $BIN_DIR/cdx"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo "Add $BIN_DIR to PATH to run cdx from anywhere." >&2
    ;;
esac
