"""Repository attribution captured by the trusted launcher, separate from cwd."""

import json
import ntpath
import os
import posixpath
import subprocess
from pathlib import PureWindowsPath

from .errors import CdxError
from .tray_logics import _repository_root

PROJECT_SOURCES = {"git", "operator", "operator_mapping", "run_report"}


def canonical_project(value):
    """Validate recorded identities without consulting a possibly deleted checkout."""
    return (isinstance(value, str) and bool(value.strip()) and "\x00" not in value
            and ((posixpath.isabs(value) and posixpath.normpath(value) == value)
                 or (PureWindowsPath(value).is_absolute() and ntpath.normpath(value) == value)))


def recorded_project(entry):
    value = entry.get("project")
    source = entry.get("project_source")
    return value if canonical_project(value) and isinstance(source, str) and source in PROJECT_SOURCES else None


def resolve_project(cwd, explicit=None):
    """Resolve before isolation. Never infer clone provenance from remote URLs."""
    if explicit is not None:
        if not canonical_project(explicit):
            raise CdxError("--project must be an absolute canonical source repository path.")
        return {"project": explicit, "project_source": "operator"}
    root = _repository_root(cwd)
    if root:
        if os.path.isdir(os.path.join(root, ".git")):
            return {"project": root, "project_source": "git"}
        try:
            # Ignore ambient Git overrides: this lookup belongs to the launch cwd.
            env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            common = subprocess.run(["git", "-C", root, "rev-parse", "--git-common-dir"],
                                    env=env, capture_output=True, text=True, timeout=5, check=True).stdout.strip()
            common = os.path.realpath(os.path.join(root, common))
            if os.path.isdir(common):
                return {"project": os.path.dirname(common) if os.path.basename(common) == ".git" else common,
                        "project_source": "git"}
        except (OSError, subprocess.SubprocessError):
            pass
    return {"project": None, "project_source": "unknown"}


def load_mapping(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise CdxError(f"Cannot read project mapping: {error}") from error
    if (not isinstance(data, dict) or set(data) != {"version", "projects"}
            or type(data["version"]) is not int or data["version"] != 1 or not isinstance(data["projects"], list)):
        raise CdxError("Invalid project mapping: expected version 1 and a projects array.")
    projects = {}
    for item in data["projects"]:
        if (not isinstance(item, dict) or set(item) != {"run_id", "project"}
                or not isinstance(item["run_id"], str) or not item["run_id"].strip()
                or not canonical_project(item["project"])):
            raise CdxError("Invalid project mapping: each entry needs an exact run_id and absolute canonical project path.")
        if item["run_id"] in projects and projects[item["run_id"]] != item["project"]:
            raise CdxError(f"Conflicting project mappings for run {item['run_id']}.")
        projects[item["run_id"]] = item["project"]
    return projects
