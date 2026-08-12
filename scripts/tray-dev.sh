#!/usr/bin/env bash
# Load the local macOS tray build, or return to the installed companion.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_APP="$ROOT/tray/target/release/CDX.app"
CDX="$ROOT/bin/cdx"

usage() {
  printf 'Usage: %s load|unload\n' "$0" >&2
  exit 2
}

stop_companion() {
  python3 - <<'PY'
from src.tray_restart import stop_running_companion

result = stop_running_companion()
if result["was_running"] and not result["stopped"]:
    raise SystemExit(result["reason"])
PY
}

running_command() {
  python3 - <<'PY'
import subprocess
from src.tray_instance import companion_instance

pid = companion_instance().get("pid")
if not pid:
    raise SystemExit("Tray companion did not register as running.")
print(subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True).strip())
PY
}

installed_companion() {
  python3 - <<'PY'
import os
from src.config import get_cdx_home
from src.tray_install import companion_path

path, source = companion_path(get_cdx_home(), env=os.environ)
if source != "installed" or not path or not os.path.exists(path):
    raise SystemExit("Installed tray companion is unavailable; refusing to stop the current tray.")
print(path)
PY
}

[ "$(uname -s)" = "Darwin" ] || { printf 'tray-dev: macOS only\n' >&2; exit 1; }
[ "$#" = 1 ] || usage
cd "$ROOT"

case "$1" in
  load)
    ./scripts/build-tray.sh --dev
    stop_companion
    CDX_TRAY_CDX="$CDX" open -n "$DEV_APP"
    sleep 1
    command="$(running_command)"
    [[ "$command" == "$DEV_APP/Contents/MacOS/cdx-tray" ]] \
      || { printf 'tray-dev: expected development companion, got %s\n' "$command" >&2; exit 1; }
    printf 'Development tray loaded: %s\n' "$DEV_APP"
    ;;
  unload)
    installed_companion >/dev/null
    stop_companion
    "$CDX" tray launch
    sleep 1
    command="$(running_command)"
    [[ "$command" == *"/.cdx/tray/companion/CDX.app/Contents/MacOS/cdx-tray" ]] \
      || { printf 'tray-dev: expected installed companion, got %s\n' "$command" >&2; exit 1; }
    printf 'Installed tray restored.\n'
    ;;
  *) usage ;;
esac
