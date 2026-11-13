"""Pre-accept the folder-trust, hook-review and Codex update prompts of a cdx launch.

An agent started through cdx must not stop on "Do you trust this folder?" or on
Codex's "Hooks need review" screen: nobody may be at the terminal. Two launch
settings, each on unless set off, make cdx record the answer in the provider's
own configuration inside the session's home, the same record the provider
writes when a person accepts the prompt. `auto_trust_folder`:

- Claude Code: `projects[<folder>].hasTrustDialogAccepted` in `<home>/.claude.json`.
- Codex: `[projects."<folder>"] trust_level = "trusted"` in `<home>/config.toml`.
- Antigravity: `trustedWorkspaces` in `<home>/.gemini/antigravity-cli/settings.json`.

`auto_trust_hooks`: Codex alone reviews hooks separately; for every hook it
reports as untrusted or modified, `[hooks.state."<key>"] trusted_hash` in
`<home>/config.toml`. Codex computes those hashes itself, so cdx asks its
app-server (`hooks/list`) and writes through it (`config/batchWrite`). Claude
Code and Antigravity have no separate hook review: their hooks follow folder trust.

`codex_update_prompt` (off unless set on): cdx updates Codex itself (`cdx update
all`), so its startup "Update available" screen is one more stop. cdx keeps
`check_for_update_on_startup` in `<home>/config.toml` equal to this setting.

Each write is a merge (other settings are kept), happens only when something is
missing, and goes through the provider's writer or an atomic rename.
"""

import os

from .agent_notify import _read_json, _write_json
from .antigravity_status import _directory as antigravity_directory

PENDING_HOOK_STATES = ("untrusted", "modified")


def auto_trust_folder(session):
    return (session.get("launch") or {}).get("auto_trust_folder") is not False


def auto_trust_hooks(session):
    return (session.get("launch") or {}).get("auto_trust_hooks") is not False


def codex_update_prompt(session):
    return (session.get("launch") or {}).get("codex_update_prompt") is True


def trust_paths(cwd=None):
    """The folder as given and as resolved: a provider may key it either way."""
    path = os.path.abspath(cwd or os.getcwd())
    return list(dict.fromkeys([path, os.path.realpath(path)]))


def ensure_trusted(session, cwd=None, env=None, popen_factory=None):
    """Record trust for `cwd` in this session's provider config.

    Returns None when the provider will not ask, or a short reason when the
    trust could not be recorded (the launch goes on either way).
    """
    folder, hooks = auto_trust_folder(session), auto_trust_hooks(session)
    home = session.get("authHome") or session.get("sessionRoot") or session.get("codexHome")
    if not home:
        return None
    paths = trust_paths(cwd)
    provider = session.get("provider")
    if provider == "claude" and folder:
        return _trust_claude(home, paths)
    if provider == "antigravity" and folder:
        return _trust_antigravity(home, paths)
    if provider == "codex":
        return _trust_codex(home, paths, {**os.environ, **(env or {})}, popen_factory, folder=folder, hooks=hooks,
                            update_prompt=codex_update_prompt(session))
    return None


def claude_project_key(folder):
    # Claude Code keys Windows folders with forward slashes (C:/Users/...).
    return folder.replace("\\", "/") if os.name == "nt" else folder


def _trust_claude(home, paths):
    path = os.path.join(home, ".claude.json")
    document = _read_json(path)
    if document is None:
        return "unreadable .claude.json"
    projects = document.get("projects")
    projects = projects if isinstance(projects, dict) else {}
    changed = False
    for key in map(claude_project_key, paths):
        entry = projects.get(key)
        entry = entry if isinstance(entry, dict) else {}
        if entry.get("hasTrustDialogAccepted") is not True:
            projects[key] = {**entry, "hasTrustDialogAccepted": True}
            changed = True
    if not changed:
        return None
    document["projects"] = projects
    return None if _write_json(path, document) else "cannot write .claude.json"


def _trust_antigravity(home, paths):
    path = os.path.join(antigravity_directory(home), "settings.json")
    settings = _read_json(path)
    trusted = None if settings is None else settings.get("trustedWorkspaces", [])
    if not isinstance(trusted, list):
        return "unreadable Antigravity settings.json"
    missing = [folder for folder in paths if folder not in trusted]
    if not missing:
        return None
    settings["trustedWorkspaces"] = [*trusted, *missing]
    return None if _write_json(path, settings) else "cannot write Antigravity settings.json"


def _codex_config(home):
    """The profile's config.toml ({} when absent), or None when it cannot be parsed here."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return None
    try:
        with open(os.path.join(home, "config.toml"), "rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None


def _codex_config_edits(config, paths, folder, update_prompt):
    """The edits still missing; every one of them when the config is unknown."""
    projects = (config or {}).get("projects") or {}
    untrusted = [path for path in paths if config is None or not isinstance(projects.get(path), dict)
                 or projects[path].get("trust_level") != "trusted"] if folder else []
    edits = []
    if untrusted:
        edits.append({"keyPath": "projects", "mergeStrategy": "upsert",
                      "value": {path: {"trust_level": "trusted"} for path in untrusted}})
    # Codex checks for updates unless the key says otherwise.
    if config is None or config.get("check_for_update_on_startup", True) is not update_prompt:
        edits.append({"keyPath": "check_for_update_on_startup", "mergeStrategy": "replace", "value": update_prompt})
    return edits


def _pending_hook_state(listed):
    """`hooks.state` entries approving every hook Codex would ask to review."""
    state = {}
    for entry in ((listed or {}).get("result") or {}).get("data") or []:
        for hook in entry.get("hooks") or []:
            if hook.get("trustStatus") not in PENDING_HOOK_STATES or not hook.get("key"):
                continue
            # A plugin hook's hash is `<definition>/<plugin content>`, persisted as two keys.
            trusted_hash, _, content_hash = str(hook.get("currentHash") or "").partition("/")
            if trusted_hash:
                state[hook["key"]] = {"trusted_hash": trusted_hash,
                                      **({"trusted_content_hash": content_hash} if content_hash else {})}
    return state


def _trust_codex(home, paths, env=None, popen_factory=None, timeout=10, folder=True, hooks=True, update_prompt=False):
    from .codex_usage import codex_app_server, codex_initialize_params

    def written(response):
        return bool(response) and not response.get("error")

    edits = _codex_config_edits(_codex_config(home), paths, folder, update_prompt)
    if not (edits or hooks):
        return None
    try:
        with codex_app_server(home, timeout=timeout, popen_factory=popen_factory, env=env) as request:
            if not written(request("initialize", codex_initialize_params())):
                return "codex app-server did not start"
            # Folder first: Codex lists a project's own hooks only once it is trusted.
            if edits and not written(request("config/batchWrite", {"edits": edits})):
                return "codex refused the config write"
            if not hooks:
                return None
            # A Codex without `hooks/list` has no hook review to answer.
            state = _pending_hook_state(request("hooks/list", {"cwds": [paths[0]]}))
            if state and not written(request("config/batchWrite", {"edits": [{
                    "keyPath": "hooks.state", "mergeStrategy": "upsert", "value": state}]})):
                return "codex refused the hook approvals"
    except (OSError, ValueError) as error:
        return f"codex app-server failed: {error}"
    return None
