"""Linux workspace confinement shared with the cdx-manager integration patch.

Expose tools, caches and one checkout, never the operator's home or host processes.
Provider authentication is the only credential deliberately passed to the provider.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

CACHE = Path.home() / ".cdx" / "shared-cache"


def clean_env(source: dict) -> dict:
    allowed = ("PATH", "LANG", "LC_ALL", "TERM", "TZ")
    env = {key: source[key] for key in allowed if key in source}
    env.update(HOME="/home/agent", XDG_CONFIG_HOME="/home/agent/.config",
               XDG_CACHE_HOME="/cache", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
               GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="credential.helper", GIT_CONFIG_VALUE_0="",
               GH_CONFIG_DIR="/home/agent/.config/gh", NPM_CONFIG_CACHE="/cache/npm",
               PIP_CACHE_DIR="/cache/pip", UV_CACHE_DIR="/cache/uv",
               PLAYWRIGHT_BROWSERS_PATH="/cache/playwright", CI="1")
    return env


def sandbox_command(command: list[str], tree: Path, *, network: bool, writable: bool = True,
                    source: dict | None = None, auth_home: str = "", provider: str = "") -> tuple[list[str], dict]:
    source = os.environ if source is None else source
    binary = shutil.which(command[0], path=source.get("PATH"))
    bwrap = shutil.which("bwrap", path=source.get("PATH"))
    if not binary or not bwrap:
        raise RuntimeError("Workspace isolation requires bubblewrap and " + command[0])
    if tree.is_symlink() or not tree.is_dir():
        raise RuntimeError("Workspace must be a directory")
    tree = tree.resolve()
    CACHE.mkdir(parents=True, exist_ok=True)
    args = [bwrap, "--die-with-parent", "--new-session", "--unshare-all", "--cap-drop", "ALL"]
    # The provider needs transport even when its own tool sandbox denies network.
    if network or provider:
        args += ["--share-net"]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/home/agent"]
    # An allowlist avoids overlooking another secret file or a credential symlink.
    paths = [Path(p) for p in ("/usr", "/bin", "/sbin", "/lib", "/lib64")]
    home = Path.home()
    paths += [home / ".nvm", home / ".local/bin", home / ".local/share/claude",
              home / ".local/share/uv"]
    for path in paths:
        if path.exists():
            args += ["--ro-bind", str(path), str(path)]
    for path in ("/etc/ssl", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf", "/etc/ld.so.cache",
                 "/etc/fonts", "/etc/passwd", "/etc/group", "/etc/alternatives"):
        if Path(path).exists():
            args += ["--ro-bind", path, path]
    # Fail closed for a provider installed outside the explicitly permitted toolchains.
    resolved = Path(binary).resolve()
    if not any(resolved.is_relative_to(p.resolve()) for p in paths if p.exists()):
        raise RuntimeError("Executable is outside the permitted toolchains: " + str(resolved))
    args += ["--bind", str(CACHE), "/cache", "--bind" if writable else "--ro-bind", str(tree), str(tree)]
    marker = tree / ".git"
    if marker.is_file():
        text = marker.read_text().strip()
        if marker.is_symlink() or not text.startswith("gitdir: "):
            raise RuntimeError("Invalid worktree Git marker")
        gitdir = (tree / text.removeprefix("gitdir: ")).resolve()
        common = (gitdir / (gitdir / "commondir").read_text().strip()).resolve()
        # A writable marker must never turn into an arbitrary host-directory mount.
        if (common.name != ".git" or gitdir.parent != common / "worktrees"
                or common.is_relative_to(tree) or common.is_relative_to(CACHE.resolve())
                or Path((gitdir / "gitdir").read_text().strip()).resolve() != marker):
            raise RuntimeError("Invalid external worktree Git directory")
        args += ["--ro-bind", str(marker), str(marker), "--ro-bind", str(common), str(common),
                 "--tmpfs", str(common / "worktrees"), "--ro-bind", str(gitdir), str(gitdir),
                 "--ro-bind", "/dev/null", str(common / "config"),
                 "--tmpfs", str(common / "hooks")]
        if (gitdir / "config.worktree").exists():
            args += ["--ro-bind", "/dev/null", str(gitdir / "config.worktree")]
    elif marker.exists():
        raise RuntimeError("Expected an isolated git worktree")
    env = clean_env(source)
    if provider == "codex":
        env["CODEX_HOME"] = "/home/agent/.codex"
        args += ["--ro-bind", str(Path(auth_home) / "auth.json"), "/home/agent/.codex/auth.json"]
    elif provider == "claude":
        token = source.get("CLAUDE_CODE_OAUTH_TOKEN")
        if not token:
            raise RuntimeError("Isolated Claude runs require a cdx OAuth setup token")
        env.update(CLAUDE_CODE_OAUTH_TOKEN=token, CLAUDE_CODE_SUBPROCESS_ENV_SCRUB="1",
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    elif provider:
        raise RuntimeError("Unsupported isolated provider: " + provider)
    args += ["--chdir", str(tree), "--", binary, *command[1:]]
    return args, env
