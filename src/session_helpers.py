"""Helpers shared by more than one session-service concern group.

Split out of session_service.py ahead of the file split: these are the ten
helpers the coupling measurement found reachable from two or more groups, plus
the four constants they read. Anything reached from a single group stays with
that group. Re-exported by session_service, so callers and tests that name
them there keep working.
"""

import os
import sys
from datetime import datetime
from urllib.parse import quote

from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDERS
from .errors import CdxError

DEFAULT_PROVIDER = PROVIDER_CODEX

ALLOWED_PROVIDERS = set(PROVIDERS)

MAX_SESSION_NAME_LENGTH = 64

RESERVED_SESSION_NAMES = {
    "add",
    "can-resume",
    "clean",
    "context",
    "configs",
    "cp",
    "disable",
    "disk",
    "doctor",
    "enable",
    "export",
    "fast",
    "help",
    "handoff",
    "history",
    "import",
    "last",
    "label",
    "login",
    "logout",
    "memory",
    "model",
    "mv",
    "next",
    "notify",
    "perm",
    "power",
    "ready",
    "repair",
    "reset",
    "resume",
    "ren",
    "rename",
    "rmv",
    "run",
    "select",
    "config",
    "set",
    "stats",
    "status",
    "unset",
    "update",
    "view",
    "version",
    "--help",
    "-h",
    "--version",
    "-v",
}

def _encode(name):
    return quote(name, safe="")

def _ensure_private_dir(path):
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        return
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass

def _get_global_codex_home(env=None):
    env = env or os.environ
    return env.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")

def _local_now_iso():
    return datetime.now().astimezone().isoformat()

def _process_is_running(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True

def _normalize_provider(provider):
    value = provider or DEFAULT_PROVIDER
    if value not in ALLOWED_PROVIDERS:
        raise CdxError(f"Unsupported provider: {value}")
    return value

def _runtime_is_active(runtime):
    return (
        isinstance(runtime, dict)
        and runtime.get("status") == "running"
        and _process_is_running(runtime.get("pid"))
    )

def _validate_new_session_name(name):
    if not name:
        raise CdxError("Session name is required")
    if str(name) != str(name).strip():
        raise CdxError("Session name cannot start or end with whitespace")
    if str(name) in (".", ".."):
        raise CdxError("Session name cannot be . or ..")
    if len(str(name)) > MAX_SESSION_NAME_LENGTH:
        raise CdxError(f"Session name is too long (max {MAX_SESSION_NAME_LENGTH} characters)")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in str(name)):
        raise CdxError("Session name cannot contain control characters")
    if name in RESERVED_SESSION_NAMES:
        raise CdxError(f"Session name is reserved: {name}")

def _get_session_root(base_dir, name):
    return os.path.join(base_dir, "profiles", _encode(name))

def _get_session_auth_home(base_dir, name, provider):
    root = _get_session_root(base_dir, name)
    if provider == PROVIDER_CLAUDE:
        return os.path.join(root, "claude-home")
    if provider == PROVIDER_ANTIGRAVITY:
        return os.path.join(root, "antigravity-home")
    return root
