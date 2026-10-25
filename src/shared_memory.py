"""One Claude auto-memory per project, shared by the profiles that opt in.

Claude Code keeps its auto-memory under the profile home
(`.claude/projects/<project>/memory`), and cdx gives every profile its own
home, so a fact learned on one account is unknown on the next. A profile with
`shared_memory` on gets that directory as a symlink into
`<cdx home>/shared-memory/<project>`, which every such profile reads and
writes.

Nothing is ever deleted. A profile's existing memory is copied into the store
and the original directory kept beside it as `memory.pre-cdx-<time>`. Two
files with the same name and different content are a conflict: the profile
is left as it was and the caller says which files to merge by hand. The
`MEMORY.md` index is the one exception, since it is one line per memory: its
lines are merged, store first.
"""

import filecmp
import os
import re
import shutil
import time

INDEX_NAME = "MEMORY.md"
#: Claude Code shortens longer project folder names with a hash cdx cannot
#: reproduce, so those projects are left alone rather than guessed at.
MAX_PROJECT_NAME = 200


def claude_project_name(cwd):
    """The folder name Claude Code files a working directory under."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd))


def store_dir(base_dir, project):
    return os.path.join(base_dir, "shared-memory", project)


def link(auth_home, base_dir, cwd, now=None):
    """Point the profile's memory for `cwd` at the shared store.

    Returns (status, detail): `linked` (done now or already), `skipped`
    (project name too long, or the memory path is a link cdx did not make),
    `conflict` (detail lists the files), `unsupported` (no symlinks here).
    """
    project = claude_project_name(cwd)
    if len(project) > MAX_PROJECT_NAME:
        return "skipped", "project path too long to match Claude Code's folder name"
    store = store_dir(base_dir, project)
    memory = os.path.join(auth_home, ".claude", "projects", project, "memory")
    if os.path.islink(memory):
        if os.path.realpath(memory) == os.path.realpath(store):
            return "linked", memory
        return "skipped", f"{memory} already links elsewhere"
    os.makedirs(store, exist_ok=True)
    if os.path.isdir(memory):
        conflicts = _conflicts(memory, store)
        if conflicts:
            return "conflict", conflicts
        _merge_into(memory, store)
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime(time.time() if now is None else now))
        os.rename(memory, f"{memory}.pre-cdx-{stamp}")
    else:
        os.makedirs(os.path.dirname(memory), exist_ok=True)
    try:
        os.symlink(store, memory, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        return "unsupported", str(error)
    return "linked", memory


def _conflicts(memory, store):
    found = []
    for name in sorted(os.listdir(memory)):
        source, target = os.path.join(memory, name), os.path.join(store, name)
        if not os.path.exists(target) or name == INDEX_NAME:
            continue
        if os.path.isdir(source) or os.path.isdir(target) or not filecmp.cmp(source, target, shallow=False):
            found.append(name)
    return found


def _merge_into(memory, store):
    for name in os.listdir(memory):
        source, target = os.path.join(memory, name), os.path.join(store, name)
        if name == INDEX_NAME and os.path.exists(target):
            _merge_index(source, target)
        elif not os.path.exists(target):
            if os.path.isdir(source):
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)


def _merge_index(source, target):
    with open(target, encoding="utf-8") as handle:
        kept = handle.read().splitlines()
    with open(source, encoding="utf-8") as handle:
        added = [line for line in handle.read().splitlines() if line.strip() and line not in kept]
    if added:
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("\n".join(kept + added) + "\n")
