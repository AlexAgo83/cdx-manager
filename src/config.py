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

# A budget is a ceiling, so the only bound worth enforcing is the one a caller
# could cross by accident. Zero and negatives express nothing; the upper bound
# catches a misplaced decimal rather than stating a policy. Defined here, not in
# each parser, because `cdx set` and `cdx run` validating the same setting from
# separate literals is how they came to disagree before.
MAX_LAUNCH_BUDGET_USD = 10000

MAX_LAUNCH_EXTRA_ARGS_LENGTH = 512


def split_extra_args(value):
    """Passthrough arguments as an argv list, or None if the string is malformed.

    POSIX splitting on every platform, deliberately. The alternative - following
    the host's own quoting rules - would make the same `cdx set` mean different
    things on Windows and on macOS, and these strings travel between machines
    through `cdx export`. One rule everywhere is worth more than matching the
    local shell, especially since cdx never invokes a shell: the result is
    passed as argv, so nothing here is ever re-interpreted.
    """
    import shlex

    if value is None:
        return None
    try:
        return shlex.split(str(value), posix=True)
    except ValueError:
        return None


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
