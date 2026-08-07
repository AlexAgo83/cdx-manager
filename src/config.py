import os
from pathlib import Path

PROVIDER_CODEX = "codex"
PROVIDER_CLAUDE = "claude"
PROVIDER_ANTIGRAVITY = "antigravity"
PROVIDER_OLLAMA = "ollama"
PROVIDERS = (PROVIDER_CODEX, PROVIDER_CLAUDE, PROVIDER_ANTIGRAVITY, PROVIDER_OLLAMA)

# The values cdx accepts, defined once. Every validator, normalizer, and
# `cdx schema --json` derives from these. They used to be restated in
# cli_args, provider_runtime, and session_service — six copies for two
# concepts — which let `cdx set` and `cdx run` disagree about the same
# setting, and let `cdx schema --json` describe only one of them.
# config.py owns them because it is the leaf: everything imports it and it
# imports nothing of ours, so no ownership choice here can create a cycle.

# Ordered weakest to strongest; the order is meaningful for comparisons such
# as `--min-reasoning-effort`, so consumers must not re-sort it.
REASONING_EFFORT_VALUES = ("minimal", "low", "medium", "high", "xhigh")

# The canonical permissions, i.e. what cdx stores and what providers are
# mapped from.
PERMISSION_VALUES = ("review", "default", "auto", "full")

# Provider-native spellings accepted as input and normalized to the
# canonical value above, so a user can paste what their provider calls it.
PERMISSION_ALIASES = {
    "workspace-write": "default",
    "read-only": "review",
    "danger-full-access": "full",
}

# Everything accepted as input for a permission, canonical values first.
PERMISSION_INPUT_VALUES = PERMISSION_VALUES + tuple(PERMISSION_ALIASES)


def normalize_permission(value):
    """Canonical form of a permission input, or None if it is not one.

    Returning None rather than raising keeps the error message and error code
    the caller's business: `cdx run` and `cdx set` word their failures
    differently, but they must agree on what is valid.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    text = PERMISSION_ALIASES.get(text, text)
    return text if text in PERMISSION_VALUES else None


def get_cdx_home(env=None):
    if env is None:
        env = os.environ
    return env.get("CDX_HOME", str(Path.home() / ".cdx"))
