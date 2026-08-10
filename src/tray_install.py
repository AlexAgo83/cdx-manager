"""Where an installed tray companion lives, and what was recorded about it.

`cdx tray install` is item_081's job; this module owns the shape of what it
writes so `launch` and `uninstall` can already be truthful about a companion
that is or is not there. Uninstall must remove only what install recorded, so
the record is the contract, not a guess about where files might be.
"""
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request

from .tray_shortcut import create as create_shortcut

STATE_VERSION = 1

RELEASE_ASSET_URL = "https://github.com/AlexAgo83/cdx-manager/releases/download/v{version}/{asset}"
CHECKSUM_LEDGER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "checksums",
    "release-archives.json",
)

# One asset per OS and architecture. The companion is a native binary, so a
# wrong pick is not a degraded experience, it is a file that cannot execute.
TARGETS = {
    ("Darwin", "arm64"): "aarch64-apple-darwin",
    ("Darwin", "x86_64"): "x86_64-apple-darwin",
    ("Windows", "AMD64"): "x86_64-pc-windows-gnu",
    ("Linux", "x86_64"): "x86_64-unknown-linux-musl",
    ("Linux", "aarch64"): "aarch64-unknown-linux-musl",
}


class TrayInstallError(Exception):
    """Refused before anything was written. Every raise site here is a gate."""


def current_target(system=None, machine=None):
    """The release target for this machine, or None when there is no asset.

    Reported rather than guessed: installing the wrong architecture produces a
    binary that cannot run, which is a worse failure than saying so up front.
    """
    key = (system or platform.system(), machine or platform.machine())
    return TARGETS.get(key)


def asset_name(version, target):
    return f"cdx-tray-{version}-{target}.tar.gz"


def expected_checksum(version, target, ledger_path=CHECKSUM_LEDGER):
    """The published sha256 for this asset, or None when none is recorded.

    None is a refusal, not a fallback. An asset with no published checksum is
    exactly the case this gate exists for.
    """
    try:
        with open(ledger_path, encoding="utf-8") as handle:
            ledger = json.load(handle)
    except (OSError, ValueError):
        return None
    release = (ledger.get("releases") or {}).get(f"v{version}") or {}
    return (release.get("tray_assets") or {}).get(target)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url, destination):
    with urllib.request.urlopen(url, timeout=60) as response, open(destination, "wb") as handle:
        shutil.copyfileobj(response, handle)

# Every path install writes goes in here, so removal never has to guess.
def state_dir(base_dir):
    return os.path.join(base_dir, "tray")


def state_path(base_dir):
    return os.path.join(state_dir(base_dir), "install.json")


def read_state(base_dir):
    """What install recorded, or None. A damaged record reads as absent.

    Refusing to parse rather than guessing is the safe failure here: the record
    drives deletion, and a half-understood one could remove the wrong path.
    """
    try:
        with open(state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        return None
    return state


def companion_path(base_dir, env=None):
    """The companion to launch, and where that answer came from.

    `CDX_TRAY_BIN` wins so a locally built companion can be run before any
    install path exists; that is how this was developed and tested.
    """
    env = os.environ if env is None else env
    override = (env.get("CDX_TRAY_BIN") or "").strip()
    if override:
        return override, "override"
    state = read_state(base_dir)
    if state and state.get("executable"):
        return state["executable"], "installed"
    return None, "absent"


def install(base_dir, version, download=None, ledger_path=CHECKSUM_LEDGER, target=None,
            destination=None, record=True, env=None):
    """Fetch, verify, unpack, record. Every step before unpack is a refusal point.

    The checksum is verified before a single byte is unpacked, because after
    unpacking there is already something on disk to clean up and something that
    might be executed. `adr_005` makes this gate load-bearing: the companion is
    self-signed, so the published checksum is what vouches for it, not Apple and
    not Microsoft.

    Fetching through cdx rather than a browser is also what keeps the asset free
    of macOS quarantine and Windows Mark-of-the-Web, so a download link must
    never be offered as an alternative.
    """
    target = target or current_target()
    if not target:
        raise TrayInstallError(
            f"No tray companion is published for {platform.system()} {platform.machine()}."
        )
    expected = expected_checksum(version, target, ledger_path=ledger_path)
    if not expected:
        raise TrayInstallError(
            f"No published checksum for the {target} tray companion of CDX {version}. "
            "Refusing to install an asset nothing vouches for."
        )

    asset = asset_name(version, target)
    url = RELEASE_ASSET_URL.format(version=version, asset=asset)
    fetch = download or _download
    with tempfile.TemporaryDirectory(prefix="cdx-tray-") as scratch:
        archive = os.path.join(scratch, asset)
        try:
            fetch(url, archive)
        except OSError as error:
            raise TrayInstallError(f"Could not download {url}: {error}") from error

        actual = _sha256(archive)
        if actual != expected:
            raise TrayInstallError(
                f"Checksum mismatch for {asset}.\n  expected {expected}\n  got      {actual}\n"
                "Nothing was installed."
            )

        destination = destination or os.path.join(state_dir(base_dir), "companion")
        shutil.rmtree(destination, ignore_errors=True)
        os.makedirs(destination, exist_ok=True)
        installed = _extract(archive, destination)

    executable = _executable_in(destination, installed)
    if not executable:
        shutil.rmtree(destination, ignore_errors=True)
        raise TrayInstallError(f"{asset} contains no cdx-tray executable. Nothing was installed.")

    # Best-effort, and after the companion is known to be on disk: the shortcut
    # points at it. A failure here does not fail the install — the tray runs
    # either way, only its toasts would go nowhere, and doctor reports that.
    shortcut = create_shortcut(executable, env=env)

    state = {
        "version": STATE_VERSION,
        "cdx_version": version,
        "target": target,
        "asset": asset,
        "sha256": expected,
        "executable": executable,
        # Uninstall removes these and nothing else. A path CDX did not write
        # must never end up here — which is why the shortcut is recorded only
        # when it was actually created, and never merely because it exists.
        "paths": [destination] + ([shortcut["path"]] if shortcut["created"] else []),
        "shortcut": shortcut["path"] if shortcut["created"] else None,
    }
    if not record:
        # Staging: the caller promotes it and writes the record itself, so a
        # staged install never claims to be the installed one.
        return state
    os.makedirs(state_dir(base_dir), exist_ok=True)
    with open(state_path(base_dir), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return state


def _extract(archive, destination):
    """Unpack, refusing any member that would escape the destination.

    A tar entry may name `../` or an absolute path. Trusting the archive here
    would let a bad asset write anywhere the user can, which is the one thing a
    verified checksum does not protect against if verification is ever skipped.
    """
    names = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            resolved = os.path.realpath(os.path.join(destination, member.name))
            if not resolved.startswith(os.path.realpath(destination) + os.sep):
                raise TrayInstallError(
                    f"{os.path.basename(archive)} tries to write outside its install directory "
                    f"({member.name}). Nothing was installed."
                )
            if member.issym() or member.islnk():
                raise TrayInstallError(
                    f"{os.path.basename(archive)} contains a link ({member.name}). "
                    "Nothing was installed."
                )
            names.append(member.name)
        tar.extractall(destination)  # noqa: S202  (members checked above)
    return names


def _executable_in(destination, names):
    """The companion inside what was unpacked, made executable.

    A bundle wins over a bare binary, and deliberately not by relying on tar
    member order. The macOS asset contains both `CDX.app` and the executable
    inside it, and launching that inner binary directly would lose the bundle:
    no `Info.plist`, so no `LSUIElement` and no stable identity for the
    notification grant. Which of the two an ordered scan found first would then
    depend on how the archive happened to be written.

    An AppleDouble companion is not a candidate. macOS tar stores extended
    attributes as a `._name` member beside the real one, and `._CDX.app` ends in
    `.app` while being a few hundred bytes of metadata. BSD tar hides those
    members on listing because it merges them back, so an archive can look clean
    and still install one over the real bundle.
    """
    def candidate(name):
        base = os.path.basename(name.rstrip("/"))
        return base if not base.startswith("._") else ""

    bundles = [n for n in names if candidate(n).endswith(".app")]
    binaries = [n for n in names if candidate(n) in ("cdx-tray", "cdx-tray.exe")]
    for name in bundles + binaries:
        path = os.path.join(destination, name.rstrip("/"))
        if os.path.isdir(path):
            return path
        if os.path.isfile(path):
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
            return path
    return None


def staged_dir(base_dir):
    return os.path.join(state_dir(base_dir), "companion.staged")


def update(base_dir, version, download=None, ledger_path=CHECKSUM_LEDGER, target=None, probe=None):
    """Replace an installed companion without ever being left with none.

    The order is the whole point. The replacement is downloaded, verified and
    proved to start *before* the working one is touched, so a bad asset, a
    truncated download or a binary that cannot execute on this machine costs an
    error message rather than a tray the user can no longer start.

    A staged directory left behind is a recoverable state, not corruption:
    `cdx tray doctor` reports it and the next update replaces it.
    """
    previous = read_state(base_dir)
    if not previous:
        raise TrayInstallError("No tray companion is installed, so there is nothing to update.")

    staged = staged_dir(base_dir)
    shutil.rmtree(staged, ignore_errors=True)
    fresh = install(
        base_dir, version,
        download=download, ledger_path=ledger_path, target=target,
        destination=staged, record=False,
    )

    # Proving it starts is what separates staging from hoping. A binary for the
    # wrong architecture, or one missing a library, fails here rather than after
    # the working companion is gone.
    runner = probe or _probe
    if not runner(fresh["executable"]):
        shutil.rmtree(staged, ignore_errors=True)
        raise TrayInstallError(
            f"The staged tray companion for CDX {version} did not start. "
            "The installed one was left untouched."
        )

    live = os.path.join(state_dir(base_dir), "companion")
    retired = os.path.join(state_dir(base_dir), "companion.previous")
    shutil.rmtree(retired, ignore_errors=True)
    if os.path.isdir(live):
        os.rename(live, retired)
    os.rename(staged, live)
    # Only now is the previous one retired.
    shutil.rmtree(retired, ignore_errors=True)

    state = {
        **fresh,
        "executable": fresh["executable"].replace(staged, live, 1),
        "paths": [live],
    }
    with open(state_path(base_dir), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return {"state": state, "replaced": previous.get("cdx_version")}


def _probe(executable):
    """Does this companion start at all? `--print` exits non-zero when CDX is
    unavailable, which is not the question here, so any completed run counts."""
    try:
        subprocess.run(  # noqa: S603  (path comes from our own install state)
            launch_command(executable) + ["--print"],
            capture_output=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def interrupted_update(base_dir):
    """A staged directory nobody promoted: an update that died mid-flight."""
    return os.path.isdir(staged_dir(base_dir))


def uninstall(base_dir):
    """Remove exactly what install recorded, and the record itself."""
    state = read_state(base_dir)
    if not state:
        return None
    removed = []
    for path in state.get("paths") or []:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path)
        elif os.path.exists(path):
            os.remove(path)
            removed.append(path)
    try:
        os.remove(state_path(base_dir))
    except OSError:
        pass
    return {"removed": removed, "state": state}


def launch_command(executable):
    """How to start the companion without holding on to it.

    On macOS an installed companion is an app bundle, and `open` hands it to
    launchd so it survives this process exiting. A bare binary is spawned
    directly, which is what a development build is.
    """
    if platform.system() == "Darwin" and executable.endswith(".app"):
        return ["open", "-a", executable]
    return [executable]
