"""Best-effort, bounded discovery of the current user's Linux agent processes."""

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

PROC_ROOT = Path("/proc")
MAX_PROCESSES = 8192
MAX_FILE_BYTES = 262144


def _read(path, limit=MAX_FILE_BYTES):
    # Check the opened file before reading: a symlink must not expose another
    # user's session or environment, even when the directory is ours.
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
            raise ValueError("unowned_file")
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("file_limit")
    return data.decode("utf-8")


def _provider(executable, argv):
    name = Path(executable).name
    names = {"claude": "claude", "codex": "codex", "agy": "antigravity", "ollama": "ollama"}
    if name in names:
        return names[name]
    path = Path(executable)
    if path.parent.name == "versions" and path.parent.parent.name == "claude" and Path(argv[0]).name == "claude":
        return "claude"
    if name in ("node", "nodejs", "bun") and len(argv) > 1:
        script = Path(argv[1])
        if script.name == "cli.js" and script.parent.name == "claude-code":
            return "claude"
        if script.name in ("agy", "agy.js"):
            return "antigravity"
    return None


def _launch_id(argv):
    for index, arg in enumerate(argv):
        if arg.startswith("--session-id="):
            return arg.split("=", 1)[1] or None
        if arg in ("--session-id", "--resume") and index + 1 < len(argv):
            value = argv[index + 1]
            return value if value and not value.startswith("-") else None
        if arg == "--":
            break
    return None


def _profile_matches(session, provider, env):
    if session["provider"] != provider or not session.get("authHome"):
        return False
    home = os.path.abspath(session["authHome"])
    if provider == "codex":
        return env.get("CODEX_HOME") == home
    if provider == "claude" and env.get("CLAUDE_CONFIG_DIR"):
        return env["CLAUDE_CONFIG_DIR"] in (home, os.path.join(home, ".claude"))
    return env.get("HOME") == home


def _conversation(provider, env, pid):
    if provider != "claude":
        return None, "current_conversation_unavailable"
    home = env.get("CLAUDE_CONFIG_DIR") or (os.path.join(env["HOME"], ".claude") if env.get("HOME") else None)
    if not home or not os.path.isabs(home):
        return None, "claude_config_dir_unavailable"
    try:
        value = json.loads(_read(Path(home) / "sessions" / f"{pid}.json", 16384))
        identifier = value.get("sessionId") if isinstance(value, dict) else None
        if isinstance(identifier, str) and 0 < len(identifier) <= 256 and not any(c.isspace() for c in identifier):
            return identifier, "claude_session_file"
        return None, "claude_session_file_invalid"
    except FileNotFoundError:
        return None, "claude_session_file_missing"
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None, "claude_session_file_unavailable"


def discover_session_processes(sessions):
    """Scan at most 8192 proc entries once, with bounded reads and ancestry.

    Non-Linux systems have no reliable process evidence here and return empty
    lists. Profile/runtime records are deliberately never used as current IDs.
    """
    result = {s["name"]: [] for s in sessions}
    if sys.platform != "linux":
        return result
    processes = {}
    try:
        with os.scandir(PROC_ROOT) as entries:
            for count, entry in enumerate(entries):
                if count >= MAX_PROCESSES:
                    break
                if not entry.name.isdecimal():
                    continue
                root = PROC_ROOT / entry.name
                try:
                    if entry.stat(follow_symlinks=False).st_uid != os.getuid():
                        continue
                    fields = _read(root / "stat", 8192).rsplit(")", 1)[1].split()
                    if fields[0] in ("Z", "X", "x"):
                        continue
                    uids = next(line.split()[1:] for line in _read(root / "status", 8192).splitlines() if line.startswith("Uid:"))
                    if len(uids) != 4 or any(int(uid) != os.getuid() for uid in uids):
                        continue
                    executable = os.readlink(root / "exe")
                    processes[int(entry.name)] = {"parent": int(fields[1]), "ticks": int(fields[19]),
                                                  "executable": executable, "root": root}
                except (OSError, ValueError, IndexError, StopIteration, UnicodeError):
                    continue
    except OSError:
        return result
    try:
        # /proc/stat is kernel-owned public timing metadata, not user data.
        with (PROC_ROOT / "stat").open(encoding="utf-8") as handle:
            timing = handle.read(65536)
        boot = int(next(line.split()[1] for line in timing.splitlines() if line.startswith("btime ")))
        ticks = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, StopIteration):
        boot = ticks = None
    for pid, process in processes.items():
        root = process["root"]
        try:
            argv = _read(root / "cmdline").rstrip("\0").split("\0")
            provider = _provider(process["executable"], argv)
            if not provider:
                continue
            env = dict(item.split("=", 1) for item in _read(root / "environ").split("\0") if "=" in item)
            matches = [s for s in sessions if _profile_matches(s, provider, env)]
            if len(matches) != 1:
                continue
            wrapper = None
            parent = process["parent"]
            for _ in range(16):
                ancestor = processes.get(parent)
                if not ancestor:
                    break
                if Path(ancestor["executable"]).name == "script":
                    wrapper = parent
                    break
                parent = ancestor["parent"]
            try:
                cwd = os.readlink(root / "cwd")
            except OSError:
                cwd = None
            conversation, source = _conversation(provider, env, pid)
            started = datetime.fromtimestamp(boot + process["ticks"] / ticks, timezone.utc).isoformat() if ticks else None
            # Reject exit/PID reuse during the scan before returning evidence.
            current = _read(root / "stat", 8192).rsplit(")", 1)[1].split()
            if current[0] in ("Z", "X", "x") or int(current[19]) != process["ticks"]:
                continue
            result[matches[0]["name"]].append({
                "agent_pid": pid, "wrapper_pid": wrapper, "provider": provider,
                "conversation_id": conversation, "conversation_source": source,
                "launch_conversation_id": _launch_id(argv) if provider == "claude" else None,
                "cwd": cwd, "started_at": started,
            })
        except (OSError, ValueError, IndexError, UnicodeError, OverflowError):
            continue
    for entries in result.values():
        entries.sort(key=lambda item: item["agent_pid"])
    return result
