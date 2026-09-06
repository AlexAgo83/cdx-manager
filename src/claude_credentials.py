"""Profile-scoped macOS credential access, matching Claude Code 2.1.263."""

import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from contextlib import contextmanager

from .errors import CdxError

KEYCHAIN_TIMEOUT_SECONDS = 5


def _keychain_identity(auth_home):
    if not auth_home or not os.path.isabs(auth_home):
        raise CdxError("Claude keychain access requires an absolute profile home.")
    if os.environ.get("USE_LOCAL_OAUTH") or os.environ.get("CLAUDE_CODE_CUSTOM_OAUTH_URL"):
        raise CdxError("CDX keychain operations do not support custom Claude OAuth endpoints.")
    user = os.environ.get("USER")
    if not user:
        import pwd
        user = pwd.getpwuid(os.getuid()).pw_name
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", user):
        user = "claude-code-user"
    config_dir = unicodedata.normalize("NFC", os.path.join(auth_home, ".claude"))
    suffix = hashlib.sha256(config_dir.encode("utf-8")).hexdigest()[:8]
    return user, f"Claude Code-credentials-{suffix}"


def _security(args, *, input_text=None):
    import pwd

    # HOME may already point at a profile. Always resolve the operator's actual keychain.
    try:
        env = {**os.environ, "HOME": pwd.getpwuid(os.getuid()).pw_dir}
        result = subprocess.run(["/usr/bin/security", *args], input=input_text,
                                capture_output=True, text=True, timeout=KEYCHAIN_TIMEOUT_SECONDS,
                                env=env, check=False)
    except subprocess.TimeoutExpired:
        raise CdxError("Claude keychain operation timed out; authentication was not verified.") from None
    except (OSError, KeyError, UnicodeError):
        raise CdxError("Claude keychain is unavailable; authentication was not verified.") from None
    return result


def read_keychain_credentials(auth_home):
    if sys.platform != "darwin" or not auth_home:
        return None
    user, service = _keychain_identity(auth_home)
    result = _security(["find-generic-password", "-a", user, "-s", service, "-w"])
    if result.returncode == 44:  # errSecItemNotFound, not a locked or missing keychain.
        return None
    if result.returncode != 0:
        raise CdxError("Claude keychain access failed; unlock or allow access to the profile credential.")
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise CdxError("Claude keychain credential data is malformed.") from None
    if not isinstance(data, dict):
        raise CdxError("Claude keychain credential data is malformed.")
    return data


def write_keychain_credentials(auth_home, data):
    user, service = _keychain_identity(auth_home)
    encoded = json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode("utf-8").hex()
    command = f'add-generic-password -U -a "{user}" -s "{service}" -X "{encoded}"\n'
    # ponytail: security -i has a 4096-byte line limit; use native Security APIs if larger entries are needed.
    if len(command) > 4000:
        raise CdxError("Claude profile credential exceeds the safe keychain transfer size.")
    # Credentials travel through stdin, never argv, shell text or error diagnostics.
    result = _security(["-i"], input_text=command)
    if result.returncode != 0:
        raise CdxError("Could not write the destination Claude keychain credential.")
    # security's interactive driver may exit successfully after a failed command.
    if read_keychain_credentials(auth_home) != data:
        raise CdxError("Destination Claude keychain credential verification failed.")


def delete_keychain_credentials(auth_home):
    user, service = _keychain_identity(auth_home)
    result = _security(["delete-generic-password", "-a", user, "-s", service])
    if result.returncode not in (0, 44):
        raise CdxError("Could not remove the profile's Claude keychain credential.")


@contextmanager
def copy_keychain_credentials(source_home, dest_home, *, overwrite=False):
    """Stage a profile credential and restore the destination if its operation fails."""
    if sys.platform != "darwin":
        yield False
        return
    if _keychain_identity(source_home) == _keychain_identity(dest_home):
        raise CdxError("Source and destination Claude keychain identities collide.")
    source = read_keychain_credentials(source_home)
    previous = read_keychain_credentials(dest_home)
    if previous is not None and not overwrite:
        raise CdxError("Destination already has a Claude keychain credential; refusing to overwrite it.")
    changed = source != previous
    try:
        if changed:
            if source is None:
                delete_keychain_credentials(dest_home)
            else:
                write_keychain_credentials(dest_home, source)
        yield source is not None
    except Exception:
        if changed:
            try:
                if previous is None:
                    delete_keychain_credentials(dest_home)
                else:
                    write_keychain_credentials(dest_home, previous)
            except CdxError:
                raise CdxError("Profile operation failed; destination keychain recovery is incomplete. Source credentials were retained.") from None
        raise
