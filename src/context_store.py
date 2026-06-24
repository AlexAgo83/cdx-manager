import hashlib
import os
import shlex
import subprocess
from datetime import datetime

from .errors import CdxError
from .session_store import _ensure_dir

DEFAULT_CONTEXT_TEMPLATE = """# Shared Context

## Goal

## Current State

## Decisions

## Files Changed

## Open Questions

## Next Steps
"""


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


def _workspace_key(cwd):
    normalized = os.path.realpath(cwd or os.getcwd())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return digest


def _context_dir(base_dir, cwd):
    return os.path.join(base_dir, "contexts", _workspace_key(cwd))


def get_context_path(base_dir, cwd=None):
    return os.path.join(_context_dir(base_dir, cwd), "context.md")


def get_context_meta_path(base_dir, cwd=None):
    return os.path.join(_context_dir(base_dir, cwd), "meta.json")


def read_context(base_dir, cwd=None):
    path = get_context_path(base_dir, cwd)
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""


def write_context(base_dir, content, cwd=None):
    path = get_context_path(base_dir, cwd)
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n")
    return {
        "path": path,
        "updated_at": _local_now_iso(),
        "bytes": os.path.getsize(path),
    }


def init_context(base_dir, cwd=None):
    current = read_context(base_dir, cwd)
    if current.strip():
        return {
            "path": get_context_path(base_dir, cwd),
            "created": False,
            "bytes": len(current.encode("utf-8")),
        }
    result = write_context(base_dir, DEFAULT_CONTEXT_TEMPLATE, cwd)
    return {**result, "created": True}


def clear_context(base_dir, cwd=None):
    path = get_context_path(base_dir, cwd)
    try:
        os.remove(path)
        removed = True
    except FileNotFoundError:
        removed = False
    return {"path": path, "removed": removed}


def edit_context(base_dir, cwd=None, editor=None, env=None, spawn_sync=None):
    result = init_context(base_dir, cwd)
    path = result["path"]
    env = env or os.environ
    editor = editor or env.get("VISUAL") or env.get("EDITOR")
    if not editor:
        raise CdxError("Context edit requires VISUAL or EDITOR.")
    spawn_sync = spawn_sync or subprocess.run
    argv = shlex.split(editor) + [path]
    if spawn_sync is subprocess.run:
        completed = subprocess.run(argv)
        returncode = completed.returncode
    else:
        completed = spawn_sync(argv[0], argv[1:], {"env": env})
        returncode = completed.get("returncode", 0) if isinstance(completed, dict) else getattr(completed, "returncode", 0)
    if returncode not in (0, None):
        raise CdxError(f"Context editor exited with code {returncode}")
    return {"path": path, "edited": True}


def install_context_for_session(base_dir, session, cwd=None):
    content = read_context(base_dir, cwd)
    if not content.strip():
        raise CdxError("No shared context for this workspace. Run: cdx context init or cdx context set <text>")
    auth_home = session.get("authHome") or session.get("sessionRoot")
    if not auth_home:
        raise CdxError(f"Session auth home missing for {session['name']}")
    target_path = os.path.join(auth_home, "shared-context.md")
    _ensure_dir(os.path.dirname(target_path))
    with open(target_path, "w", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n")
    return {
        "source_path": get_context_path(base_dir, cwd),
        "target_path": target_path,
        "bytes": os.path.getsize(target_path),
    }
