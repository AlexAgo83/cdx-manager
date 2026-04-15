import os
from pathlib import Path


def get_cdx_home(env=None):
    if env is None:
        env = os.environ
    return env.get("CDX_HOME", str(Path.home() / ".cdx"))
