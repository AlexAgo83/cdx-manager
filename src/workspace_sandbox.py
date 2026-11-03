"""Linux workspace confinement shared with the cdx-manager integration patch.

Expose tools, caches and one checkout, never the operator's home or host processes.
Provider authentication is the only credential deliberately passed to the provider.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path

CACHE = Path.home() / ".cdx" / "shared-cache"

# Installed before any untrusted command, in the namespace owned by pasta.
NETWORK_RULES = """table inet mission_egress {
    chain output {
        type filter hook output priority 0; policy accept;
        oif "lo" accept
        ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8,
                   169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16 } reject
        ip6 daddr { ::1, fc00::/7, fe80::/10 } reject
    }
}
"""
PUBLIC_RESOLV_CONF = "nameserver 1.1.1.1\nnameserver 9.9.9.9\n"

# Keep the trusted setup outside the agent's filesystem/PID/user namespaces.
CLAUDE_STDIN_EXEC = """
import json
import os
import sys
token = json.loads(sys.stdin.buffer.readline())
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
os.execv(sys.argv[1], sys.argv[1:])
"""

NETWORK_SETUP = r"""
import pathlib
import subprocess
import sys
import tempfile
try:
    subprocess.run([sys.argv[1], "-f", "-"], input=RULES, text=True,
                   check=True, timeout=15)
    with tempfile.TemporaryDirectory(prefix="mission-dns-") as directory:
        resolver = pathlib.Path(directory) / "resolv.conf"
        resolver.write_text(RESOLVER)
        args = sys.argv[2:]
        index = args.index("--")
        args[index:index] = ["--ro-bind", str(resolver), "/etc/resolv.conf"]
        status = subprocess.call(args)
except (OSError, subprocess.SubprocessError) as error:
    print("Isolated mission network setup failed: " + str(error), file=sys.stderr)
    sys.exit(1)
sys.exit(status)
"""


@contextmanager
def private_auth_home(auth):
    """Keep a sanitized credential in verified memory-backed, private storage."""
    location = Path('/dev/shm').resolve()
    mounts = [row.split() for row in Path('/proc/mounts').read_text().splitlines()]
    enclosing = [row for row in mounts if Path(row[1]) == location or Path(row[1]) in location.parents]
    if not enclosing or max(enclosing, key=lambda row: len(row[1]))[2] != 'tmpfs':
        raise RuntimeError('Isolated Codex runs require memory-backed /dev/shm')
    if auth.get('tokens', {}).get('refresh_token') != '':
        raise RuntimeError('Refusing a rotating sandbox credential')
    with tempfile.TemporaryDirectory(prefix='cdx-observation-', dir=location) as directory:
        path = Path(directory) / 'auth.json'
        with open(path, 'x', opener=lambda name, flags: os.open(name, flags, 0o600)) as handle:
            json.dump(auth, handle)
        (Path(directory) / 'sessions').mkdir(mode=0o700)
        yield directory


def clean_env(source: dict) -> dict:
    allowed = ("PATH", "LANG", "LC_ALL", "TERM", "TZ")
    env = {key: source[key] for key in allowed if key in source}
    env["PATH"] = source.get("PATH", os.defpath) + os.pathsep + str(Path.home() / ".local/bin")
    env.update(HOME="/home/agent", XDG_CONFIG_HOME="/home/agent/.config",
               XDG_CACHE_HOME="/cache", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
               GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="credential.helper", GIT_CONFIG_VALUE_0="",
               GH_CONFIG_DIR="/home/agent/.config/gh", NPM_CONFIG_CACHE="/cache/npm",
               PIP_CACHE_DIR="/cache/pip", UV_CACHE_DIR="/cache/uv",
               RTK_DB_PATH="/cache/rtk/history.db",
               # Cache users have different mount paths; their GC cannot identify each other's browsers.
               PLAYWRIGHT_BROWSERS_PATH="/cache/playwright", PLAYWRIGHT_SKIP_BROWSER_GC="1", CI="1")
    return env


def sandbox_command(command: list[str], tree: Path, *, network: bool, writable: bool = True,
                    source: dict | None = None, auth_home: str = "", provider: str = "", observation_home: str = "", ollama_relay: str = "", claude_token_stdin: bool = False) -> tuple[list[str], dict]:
    source = os.environ if source is None else source
    env = clean_env(source)
    binary = shutil.which(command[0], path=env["PATH"])
    bwrap = shutil.which("bwrap", path=source.get("PATH"))
    if not binary or not bwrap:
        raise RuntimeError("Workspace isolation requires bubblewrap and " + command[0])
    if tree.is_symlink() or not tree.is_dir():
        raise RuntimeError("Workspace must be a directory")
    tree = tree.resolve()
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "rtk").mkdir(exist_ok=True)
    # Provider transport uses the same restricted egress, even for read-only tools.
    online = bool(network or (provider and provider != "ollama"))
    if online:
        pasta = shutil.which("pasta", path=source.get("PATH"))
        nft = shutil.which("nft", path=os.defpath + ":/usr/sbin:/sbin")
        python = shutil.which("python3", path=source.get("PATH"))
        if not pasta or not nft or not python:
            raise RuntimeError("Isolated mission networking requires pasta (passt), nftables and python3; no shared-network fallback")
    args = [bwrap, "--die-with-parent", "--new-session"]
    # pasta already created the network namespace. A new child user namespace and
    # dropped capabilities prevent the agent from changing its ancestor's nft rules.
    args += (["--unshare-user", "--unshare-ipc", "--unshare-pid", "--unshare-uts", "--unshare-cgroup"]
             if online else ["--unshare-all"])
    args += ["--cap-drop", "ALL"]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/home/agent"]
    if provider == "claude" and claude_token_stdin:
        if not observation_home:
            raise RuntimeError("Remote Claude requires a volatile attempt home")
        args += ["--bind", observation_home, "/home/agent"]
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
        if Path(path).exists() and not (online and path == "/etc/resolv.conf"):
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
        # Use sandbox-owned parents rather than traversing private host homes.
        # Do not expose repository config (remote URLs/helpers/includes), hooks,
        # other worktrees, or the source checkout. Git remains read-only.
        private_git = Path("/home/agent/.git")
        args += ["--ro-bind", str(marker), str(marker), "--dir", str(private_git)]
        # Combine this worktree's HEAD/index with shared history, without any
        # commondir/gitdir pointers back into the host filesystem.
        for origin, names in (
            (gitdir, ["HEAD", "index", *[p.name for p in gitdir.glob("sharedindex.*")]]),
            (common, ["objects", "refs", "packed-refs", "shallow", *[p.name for p in common.glob("sharedindex.*")]]),
        ):
            for name in names:
                if (origin / name).exists():
                    args += ["--ro-bind", str(origin / name), str(private_git / name)]
        env.update(GIT_DIR=str(private_git), GIT_COMMON_DIR=str(private_git),
                   GIT_WORK_TREE=str(tree))
    elif marker.exists():
        raise RuntimeError("Expected an isolated git worktree")
    if provider == "codex":
        auth_path = Path(auth_home) / "auth.json"
        if json.loads(auth_path.read_text()).get('tokens', {}).get('refresh_token') != '':
            raise RuntimeError('Refusing a rotating sandbox credential')
        env["CODEX_HOME"] = "/home/agent/.codex"
        if observation_home:
            # Fresh, volatile attempt storage; no host profile is exposed.
            args += ["--bind", observation_home, "/home/agent/.codex/sessions"]
        args += ["--ro-bind", str(Path(auth_home) / "auth.json"), "/home/agent/.codex/auth.json"]
    elif provider == "claude":
        token = source.get("CLAUDE_CODE_OAUTH_TOKEN")
        if not token and not claude_token_stdin:
            raise RuntimeError("Isolated Claude runs require a cdx OAuth setup token")
        if claude_token_stdin:
            env["XDG_CACHE_HOME"] = "/home/agent/.cache"
            python = shutil.which("python3", path=os.defpath)
            if not python:
                raise RuntimeError("Remote Claude requires Python 3")
            command = [python, "-I", "-c", CLAUDE_STDIN_EXEC, binary, *command[1:]]
            binary = python
        else:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        env.update(CLAUDE_CODE_SUBPROCESS_ENV_SCRUB="1",
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    elif provider == "ollama":
        if not ollama_relay:
            raise RuntimeError("Isolated Ollama requires a supervisor-owned relay")
        args += ["--ro-bind", ollama_relay, "/run/cdx-ollama"]
    elif provider:
        raise RuntimeError("Unsupported isolated provider: " + provider)
    args += ["--chdir", str(tree), "--", binary, *command[1:]]
    if online:
        rules = NETWORK_RULES
        if provider == "claude" and claude_token_stdin and not network:
            # Resolve on the trusted worker before pasta replaces the DNS namespace.
            addresses = {entry[4][0] for entry in socket.getaddrinfo("api.anthropic.com", 443, type=socket.SOCK_STREAM)}
            inference = []
            for family, values in (("ip", sorted(address for address in addresses if ":" not in address)),
                                   ("ip6", sorted(address for address in addresses if ":" in address))):
                if values:
                    inference.append(f"        {family} daddr {{ {', '.join(values)} }} tcp dport 443 accept")
            if not inference:
                raise RuntimeError("No Anthropic inference addresses")
            rules = rules.replace("policy accept", "policy drop").replace(
                "        oif", "        ct state established,related accept\n        oif")
            rules = rules.replace("    }\n}", "        ip daddr { 1.1.1.1, 9.9.9.9 } udp dport 53 accept\n"
                                  "        ip daddr { 1.1.1.1, 9.9.9.9 } tcp dport 53 accept\n"
                                  + "\n".join(inference) + "\n    }\n}")
        setup = "RULES = " + repr(rules) + "\nRESOLVER = " + repr(PUBLIC_RESOLV_CONF) + "\n" + NETWORK_SETUP
        # Disable both directions explicitly: automatic host-loopback splicing
        # bypasses output filtering unless -T/-U are also disabled.
        args = [pasta, "--config-net", "--no-map-gw", "-t", "none", "-u", "none",
                "-T", "none", "-U", "none", "-q", "--", python, "-I", "-c", setup, nft, *args]
    return args, env
