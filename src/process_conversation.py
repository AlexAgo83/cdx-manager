"""Bounded Linux process identity, without guessing a selected conversation.

No argv, environment, credential stores, transcript searches or parent/child
heuristics participate in identity resolution.
"""

import hashlib
import os
import re
import sys
from pathlib import Path

PROC_ROOT = Path("/proc")
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_IDENTITY = re.compile(r"linux:(\d+):[0-9a-f]{64}")


class _Unknown(Exception):
    pass


def _bounded(path, limit=8192):
    with open(path, "rb") as handle:
        value = handle.read(limit + 1)
    if len(value) > limit:
        raise _Unknown("evidence_limit")
    return value.decode("utf-8")


def _process(pid):
    root = PROC_ROOT / str(pid)
    fields = _bounded(root / "stat").rsplit(")", 1)[1].split()
    if fields[0] in ("Z", "X", "x"):
        raise _Unknown("process_not_running")
    uids = next(line.split()[1:] for line in _bounded(root / "status").splitlines() if line.startswith("Uid:"))
    if len(uids) != 4 or any(int(uid) != os.getuid() for uid in uids):
        raise _Unknown("unrelated_user")
    executable = os.readlink(root / "exe")
    if Path(executable).name != "codex":
        raise _Unknown("unrelated_process")
    exe = os.stat(root / "exe")
    boot = _bounded(PROC_ROOT / "sys/kernel/random/boot_id").strip()
    if not re.fullmatch(_UUID, boot):
        raise _Unknown("invalid_evidence")
    digest = hashlib.sha256(f"{boot}:{pid}:{fields[19]}:{uids}:{exe.st_dev}:{exe.st_ino}".encode()).hexdigest()
    return f"linux:{pid}:{digest}"


def resolve_process_conversation(provider, auth_home, *, pid=None, process_identity=None):
    """Return explicit unknown when the native selected-thread link is absent.

    A bare PID means the process alive *now*. Persist process_identity to reject
    reuse on subsequent calls. The identity is an opaque guard, not a secret or
    authorization grant. Only Linux /proc and interactive Codex are supported.
    """
    result = {"resolution_status": "unknown", "resolution_method": None,
              "conversation_id": None, "process_identity": None, "reason": None}
    if provider != "codex" or sys.platform != "linux":
        return {**result, "reason": "unsupported_process_resolution"}
    if process_identity is not None:
        match = _IDENTITY.fullmatch(process_identity) if isinstance(process_identity, str) and len(process_identity) <= 100 else None
        if not match or pid is not None:
            return {**result, "reason": "invalid_process_identity"}
        pid = int(match[1])
    if type(pid) is not int or not 0 < pid < 2**31 or not auth_home:
        return {**result, "reason": "invalid_process_identity"}
    try:
        identity = _process(pid)
        if process_identity is not None and identity != process_identity:
            raise _Unknown("process_identity_changed")
        result["process_identity"] = identity
        if _process(pid) != identity:
            raise _Unknown("evidence_changed")
        # Even a sole writable rollout may belong to a retained thread while
        # another thread is selected but has not created its rollout. Neither
        # that descriptor nor resume argv is a native selected-thread event.
        return {**result, "reason": "native_conversation_identity_unavailable"}
    except _Unknown as exc:
        return {**result, "reason": str(exc)}
    except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration, UnicodeError, RecursionError):
        return {**result, "reason": "native_evidence_unavailable"}
