import os
from pathlib import Path

PROVIDER_CODEX = "codex"
PROVIDER_CLAUDE = "claude"
PROVIDER_ANTIGRAVITY = "antigravity"
PROVIDERS = (PROVIDER_CODEX, PROVIDER_CLAUDE, PROVIDER_ANTIGRAVITY)


def get_cdx_home(env=None):
    if env is None:
        env = os.environ
    return env.get("CDX_HOME", str(Path.home() / ".cdx"))
