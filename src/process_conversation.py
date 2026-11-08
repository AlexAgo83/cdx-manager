"""Bounded Linux process identity and profile-scoped native rollout evidence.

No argv, environment, credential stores, transcript searches or parent/child
heuristics participate in identity resolution.
"""

import hashlib
import json
import os
import re
import stat
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


def _rollout(pid, auth_home):
    """Identify a sole writable rollout; multiple native writers are ambiguous."""
    home = Path(auth_home).resolve()
    sessions = (home / "sessions").resolve()
    if not sessions.is_relative_to(home):
        raise _Unknown("profile_boundary_mismatch")
    candidates = set()
    root = PROC_ROOT / str(pid)
    with os.scandir(root / "fd") as descriptors:
        for count, descriptor in enumerate(descriptors):
            if count >= 512:
                raise _Unknown("evidence_limit")
            try:
                target = os.readlink(descriptor.path)
            except FileNotFoundError:
                continue  # Unrelated descriptors can close during enumeration.
            name = Path(target).name
            if not name.startswith("rollout-") or ".jsonl" not in name:
                continue
            flags = next(line.split()[1] for line in _bounded(root / "fdinfo" / descriptor.name).splitlines()
                         if line.startswith("flags:"))
            if int(flags, 8) & os.O_ACCMODE not in (os.O_WRONLY, os.O_RDWR):
                continue
            path = Path(target).resolve()
            if not path.is_relative_to(sessions):
                raise _Unknown("profile_boundary_mismatch")
            match = re.fullmatch(r"rollout-.*(" + _UUID + r")\.jsonl", name)
            if not match:
                raise _Unknown("invalid_native_rollout")
            file_stat = os.stat(descriptor.path)
            path_stat = path.stat()
            file_identity = (file_stat.st_dev, file_stat.st_ino)
            if not stat.S_ISREG(file_stat.st_mode) or file_identity != (path_stat.st_dev, path_stat.st_ino):
                raise _Unknown("evidence_changed")
            # Read only the metadata header of the exact open file, never a
            # transcript found by scanning the profile or matching a workspace.
            with open(descriptor.path, "rb") as handle:
                opened = os.fstat(handle.fileno())
                if (opened.st_dev, opened.st_ino) != file_identity:
                    raise _Unknown("evidence_changed")
                header = handle.readline(65537)
            if len(header) > 65536:
                raise _Unknown("evidence_limit")
            if not header.endswith(b"\n"):
                raise _Unknown("invalid_native_rollout")
            metadata = json.loads(header)
            payload = metadata.get("payload")
            if (metadata.get("type") != "session_meta" or not isinstance(payload, dict)
                    or payload.get("id") != match[1] or payload.get("source") != "cli"):
                raise _Unknown("invalid_native_rollout")
            candidates.add((match[1], path, file_identity))
    if len(candidates) > 1:
        raise _Unknown("ambiguous_native_rollouts")
    if not candidates:
        raise _Unknown("native_conversation_identity_unavailable")
    return candidates.pop()


def resolve_process_conversation(provider, auth_home, *, pid=None, process_identity=None):
    """Return public resolution fields and private exact-file evidence, if present.

    A bare PID means the process alive *now*. Persist process_identity to reject
    reuse on subsequent calls. The identity is an opaque guard, not a secret or
    authorization grant. Only Linux /proc and interactive Codex are supported.
    """
    result = {"resolution_status": "unknown", "resolution_method": None,
              "conversation_id": None, "process_identity": None, "reason": None}
    if provider != "codex" or sys.platform != "linux":
        return {**result, "reason": "unsupported_process_resolution"}, None
    if process_identity is not None:
        match = _IDENTITY.fullmatch(process_identity) if isinstance(process_identity, str) and len(process_identity) <= 100 else None
        if not match or pid is not None:
            return {**result, "reason": "invalid_process_identity"}, None
        pid = int(match[1])
    if type(pid) is not int or not 0 < pid < 2**31 or not auth_home:
        return {**result, "reason": "invalid_process_identity"}, None
    try:
        identity = _process(pid)
        if process_identity is not None and identity != process_identity:
            raise _Unknown("process_identity_changed")
        result["process_identity"] = identity
        evidence = _rollout(pid, auth_home)
        if _process(pid) != identity or _rollout(pid, auth_home) != evidence:
            raise _Unknown("evidence_changed")
        return {**result, "resolution_status": "resolved", "resolution_method": "process_open_rollout",
                "conversation_id": evidence[0]}, evidence
    except _Unknown as exc:
        return {**result, "reason": str(exc)}, None
    except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration, UnicodeError, RecursionError, AttributeError):
        return {**result, "reason": "native_evidence_unavailable"}, None
