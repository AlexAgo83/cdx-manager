import errno
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone

from .agent_notify import launch_notify_env, notifications_enabled
from .claude_credentials import read_keychain_credentials
from .claude_usage import _clean_oauth_token, _decode_jwt_claims, _secure_storage_overrides
from .codex_usage import codex_auth_lock, diagnostic_needs_codex_login, fetch_codex_rate_limit_diagnostic
from .config import (
    PROVIDER_ANTIGRAVITY,
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    PROVIDER_OLLAMA,
    REASONING_EFFORT_VALUES,
    get_cdx_home,
    split_extra_args,
)
from .errors import CdxError

LOG_ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB
TERMINAL_TITLE_SEPARATOR = " — "
# Providers redraw their own title while their TUI runs, so a single write at
# launch does not survive. Re-asserting on this interval takes the title back
# without being frequent enough to matter to the terminal.
TERMINAL_TITLE_REFRESH_SECONDS = 5.0
TERMINAL_TITLE_ACTIONS = ("launch", "resume")
# Ollama is deliberately absent: it is a local model runner, not a cdx-managed
# coding session, and its window title is left to it.
TERMINAL_TITLE_PROVIDERS = (PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_ANTIGRAVITY)
# ESC plus the C0/C1 control ranges: anything that could close the OSC string
# early or start a new escape sequence from session or directory names.
_TERMINAL_TITLE_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
AUTH_PROBE_TIMEOUT_SECONDS = 15
CODEX_INTERACTIVE_AUTH_LOCK_TIMEOUT_SECONDS = 10
AUTH_PROBE_AUTHENTICATED = "authenticated"
AUTH_PROBE_LOGGED_OUT = "logged_out"
AUTH_PROBE_DEGRADED = "degraded"
RTK_PROMPT = (
    "When running noisy shell commands, prefer RTK wrappers (`rtk <command>`) if `rtk` is available. "
    "Use raw commands when exact, unfiltered output is required."
)
LOGICS_PROMPT = (
    "When `logics-manager` is available, prefer it for Logics workflow operations: use "
    "`logics-manager status`, `health`, `audit`, and `lint` for workflow state and validation; "
    "`cdx view` for the browser viewer and focus workflows (supports `--lan`, `--focus <ref>`, `--port`, and all other viewer flags); "
    "`logics-manager sync read-doc|list-docs|search-docs|context-pack` for bounded document context; "
    "`logics-manager flow ...` for request/backlog/task lifecycle changes; and `logics-manager mcp ...` "
    "when an MCP surface is the right fit."
)
#: Turns on ollama's per-response timing block, which carries the token counts.
#: Ollama writes no provider-native transcript, so without this there is
#: nothing anywhere to read and `cdx stats` shows a permanent zero.
OLLAMA_USAGE_FLAG = "--verbose"

#: Flags cdx passes on its own initiative -- not asked for by the user and not
#: derived from a permission. Declared here rather than inline so the
#: provider-flag health check can verify they exist in the installed CLI: the
#: generalized form of GitHub issue #8, where `--experimental-yolo` was mapped
#: for ollama and that CLI never had it. A flag cdx invents is exactly as
#: capable of not existing as a flag it maps.
LAUNCH_FEATURE_ARGS = {
    PROVIDER_OLLAMA: [OLLAMA_USAGE_FLAG],
}

LAUNCH_PERMISSION_ARGS = {
    PROVIDER_CLAUDE: {
        "review": ["--permission-mode", "plan"],
        "default": ["--permission-mode", "default"],
        "auto": ["--permission-mode", "auto"],
        "full": ["--permission-mode", "bypassPermissions"],
    },
    PROVIDER_CODEX: {
        "review": ["-s", "read-only", "-a", "on-request"],
        "default": ["-s", "workspace-write", "-a", "on-request"],
        "auto": ["-s", "workspace-write", "-a", "never"],
        "full": ["-s", "danger-full-access", "-a", "never"],
    },
    PROVIDER_ANTIGRAVITY: {
        "review": ["--sandbox"],
        "full": ["--dangerously-skip-permissions"],
    },
    # ollama has no sandbox or permission concept, so it maps to nothing. The
    # entry is present and deliberately empty: that is what tells the
    # provider-flag health check there is nothing to verify here, as opposed to
    # a provider whose mapping nobody ever declared.
    PROVIDER_OLLAMA: {},
}
HEADLESS_CODEX_PERMISSION_ARGS = {
    "review": ["-s", "read-only"],
    "default": ["-s", "workspace-write"],
    "auto": ["-s", "workspace-write", "-c", 'approval_policy="never"'],
    "full": ["--dangerously-bypass-approvals-and-sandbox"],
}


def headless_permission_disables_network(provider, permission):
    """True when this provider/permission pair silently costs the run network access.

    Codex ties network access to its sandbox: every permission except `full`
    maps to `-s <sandbox>` above, and inside that sandbox a tool like `gh`
    cannot resolve DNS. The run still exits zero, so without a warning the
    caller only finds out by reading the transcript.

    Read off the same mapping the launch spec uses rather than a parallel list
    of permissions, so adding a permission cannot leave this behind.

    No permission at all is the common case, not an exemption: the launch spec
    simply appends no sandbox flag, and `codex exec` then applies its own
    sandboxed default. Only an explicit `full` actually buys network access.
    """
    if provider != PROVIDER_CODEX:
        return False
    if not permission:
        return True
    return "-s" in HEADLESS_CODEX_PERMISSION_ARGS.get(permission, [])


REDACTED_PROMPT_ARG = "[prompt redacted]"
# Documented Claude Code switch that stops it from setting and clearing the
# terminal title, leaving cdx's shared title keeper as the only writer.
CLAUDE_DISABLE_TERMINAL_TITLE_ENV = "CLAUDE_CODE_DISABLE_TERMINAL_TITLE"
CLAUDE_CLI_MODEL_ALIASES = {
    "claude-sonnet": "sonnet",
    "claude-opus": "opus",
    "claude-haiku": "haiku",
    "sonnet-latest": "sonnet",
    "opus-latest": "opus",
    "haiku-latest": "haiku",
}


def _home_env_overrides(auth_home):
    """Return env vars that point the claude CLI to the given home directory.

    On Unix, only HOME is needed. Claude Code resolves its auth files relative
    to HOME; forcing CLAUDE_CONFIG_DIR to this directory makes current Claude
    Code builds ignore otherwise valid isolated credentials. On Windows, Node.js
    resolves the home directory via USERPROFILE (and falls back to
    HOMEDRIVE+HOMEPATH), so we set all three to ensure profile isolation works
    regardless of the platform. Redirecting the home also detaches Claude
    Code's credential storage, which `_secure_storage_overrides` re-keys to
    this profile.
    """
    overrides = {
        "HOME": auth_home,
        "ANTHROPIC_CONFIG_DIR": auth_home,
        "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS": "1",
    }
    if sys.platform == "win32":
        overrides["USERPROFILE"] = auth_home
        overrides["HOMEDRIVE"] = os.path.splitdrive(auth_home)[0] or "C:"
        overrides["HOMEPATH"] = os.path.splitdrive(auth_home)[1] or auth_home
    overrides.update(_secure_storage_overrides(auth_home))
    return overrides


def _shared_tool_cache_overrides(env):
    """Pin tool download/build caches to one shared dir, outside any profile home.

    Profile isolation redirects HOME to a per-profile auth_home (see
    `_home_env_overrides`), and several dev tools resolve their cache dir from
    HOME. Left alone, that means every profile re-downloads its own copy of
    Playwright's browsers, npm/pip/uv packages, etc. `env` here is the ambient
    env, before HOME gets swapped, so `get_cdx_home(env)` resolves the same
    real per-user location regardless of which profile is launching.
    """
    shared_cache = os.path.join(get_cdx_home(env), "shared-cache")
    return {
        "PLAYWRIGHT_BROWSERS_PATH": os.path.join(shared_cache, "playwright"),
        "NPM_CONFIG_CACHE": os.path.join(shared_cache, "npm"),
        "PIP_CACHE_DIR": os.path.join(shared_cache, "pip"),
        "UV_CACHE_DIR": os.path.join(shared_cache, "uv"),
    }


def _anthropic_profile_name():
    return "default"


def _anthropic_credentials_path(auth_home):
    return os.path.join(auth_home, "credentials", f"{_anthropic_profile_name()}.json")


def _claude_env(base_env, auth_home, own_terminal_title=False):
    """Build the Claude provider environment for one cdx spawn.

    `own_terminal_title` is set by the interactive launch/resume paths, where
    cdx's title keeper owns the `session — folder` title. Claude Code redraws an
    animated busy title far more often than the keeper re-emits, so we tell it
    to leave the title alone; its in-TUI activity indicator is unaffected. The
    value is forced rather than defaulted so an ambient `0` in the operator's
    shell cannot hand the title back to Claude. Headless and auth spawns do not
    own a title and keep their previous environment.
    """
    env = {**base_env, **_home_env_overrides(auth_home)}
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.pop("CODEX_HOME", None)
    env.setdefault("ANTHROPIC_PROFILE", _anthropic_profile_name())
    if own_terminal_title:
        env[CLAUDE_DISABLE_TERMINAL_TITLE_ENV] = "1"
    return env


def _read_anthropic_oauth_token(auth_home):
    try:
        with open(_anthropic_credentials_path(auth_home), encoding="utf-8") as handle:
            credentials = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    token = credentials.get("access_token") if isinstance(credentials, dict) else None
    return _clean_oauth_token(token)


def _has_local_claude_auth(auth_home):
    try:
        with open(os.path.join(auth_home, ".claude", ".credentials.json"), encoding="utf-8") as handle:
            credentials = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    oauth = credentials.get("claudeAiOauth") if isinstance(credentials, dict) else None
    return bool(isinstance(oauth, dict) and _clean_oauth_token(oauth.get("accessToken")))


def _read_claude_launch_oauth_token(auth_home):
    if _has_local_claude_auth(auth_home):
        return None
    token = _read_anthropic_oauth_token(auth_home)
    if token and read_keychain_credentials(auth_home) is not None:
        return None
    return token


def _has_local_codex_auth(auth_home):
    try:
        with open(os.path.join(auth_home, "auth.json"), encoding="utf-8") as handle:
            auth = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    if not isinstance(auth, dict):
        return False
    tokens = auth.get("tokens")
    if not isinstance(tokens, dict):
        return False
    return any(
        _clean_oauth_token(tokens.get(name))
        for name in ("id_token", "access_token", "refresh_token")
    )


def _read_codex_account_email(auth_home):
    try:
        with open(os.path.join(auth_home, "auth.json"), encoding="utf-8") as handle:
            auth = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    tokens = auth.get("tokens") if isinstance(auth, dict) else {}
    if not isinstance(tokens, dict):
        return None
    for token_name in ("id_token", "access_token"):
        claims = _decode_jwt_claims(tokens.get(token_name))
        email = claims.get("email")
        if not email and token_name == "access_token":
            profile = claims.get("https://api.openai.com/profile") or {}
            email = profile.get("email") if isinstance(profile, dict) else None
        if email:
            return str(email).strip().lower()
    return None


def _read_codex_account_id(auth_home):
    try:
        with open(os.path.join(auth_home, "auth.json"), encoding="utf-8") as handle:
            auth = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    tokens = auth.get("tokens") if isinstance(auth, dict) else {}
    account_id = tokens.get("account_id") if isinstance(tokens, dict) else None
    if not account_id:
        return None
    return str(account_id).strip() or None


def codex_auth_diagnostic(session, spawn_sync=None, env_override=None):
    auth_home = _get_auth_home(session)
    auth_path = os.path.join(auth_home, "auth.json")
    result = {
        "auth_home": auth_home,
        "auth_json_exists": os.path.isfile(auth_path),
        "local_tokens_present": _has_local_codex_auth(auth_home),
        "account_email": _read_codex_account_email(auth_home),
        "account_id": _read_codex_account_id(auth_home),
        "live_status": "unknown",
        "live_error": None,
    }
    if not result["local_tokens_present"]:
        result["live_status"] = AUTH_PROBE_LOGGED_OUT
        return result
    diagnostic = fetch_codex_rate_limit_diagnostic(session)
    if diagnostic["ok"]:
        result["live_status"] = AUTH_PROBE_AUTHENTICATED
    elif diagnostic["reason"] == "auth_locked":
        result["live_status"] = AUTH_PROBE_DEGRADED
        result["live_error"] = "Codex authentication probe is locked by an active session."
    elif diagnostic_needs_codex_login(diagnostic):
        result["live_status"] = "login_required"
        result["live_error"] = f"Codex authentication requires login; run cdx login {session['name']}."
    else:
        result["live_status"] = "error"
        result["live_error"] = f"Codex app-server authentication probe failed ({diagnostic['reason']})."
    return result


def _read_claude_account_email(auth_home):
    config_path = os.path.join(auth_home, ".claude.json")
    try:
        with open(config_path, encoding="utf-8") as handle:
            config = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    account = config.get("oauthAccount") if isinstance(config, dict) else None
    email = account.get("emailAddress") if isinstance(account, dict) else None
    if not email:
        return None
    return str(email).strip()


def _antigravity_env_overrides(auth_home):
    overrides = {"HOME": auth_home}
    if sys.platform == "win32":
        overrides["USERPROFILE"] = auth_home
        overrides["HOMEDRIVE"] = os.path.splitdrive(auth_home)[0] or "C:"
        overrides["HOMEPATH"] = os.path.splitdrive(auth_home)[1] or auth_home
    return overrides


def _get_auth_home(session):
    return session.get("authHome") or session.get("sessionRoot") or session.get("codexHome", "")


def _get_launch_transcript_path(session):
    return os.path.join(_get_auth_home(session), "log", "cdx-session.log")


def _get_launch_transcript_dir(session):
    return os.path.join(_get_auth_home(session), "log")


def _build_launch_transcript_path(session):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return os.path.join(
        _get_launch_transcript_dir(session),
        f"cdx-session-{stamp}-{os.getpid()}.log",
    )


def _launch_power(session):
    launch = session.get("launch") or {}
    power = launch.get("reasoning_effort") or launch.get("reasoningEffort") or launch.get("power")
    if power:
        return power
    if _legacy_fast_low_effort(launch):
        return "low"
    return None


def _legacy_fast_low_effort(launch):
    return launch.get("fast") is True and launch.get("fastMode") != "service_tier"


def _codex_fast_enabled(launch):
    return launch.get("fast") is True and launch.get("fastMode") == "service_tier"


def _codex_fast_config_args(launch):
    if _codex_fast_enabled(launch):
        return ["-c", 'service_tier="fast"', "-c", "features.fast_mode=true"]
    return ["-c", 'service_tier="flex"', "-c", "features.fast_mode=false"]


def _normalize_reasoning_effort(reasoning_effort=None, power=None, usage="Unsupported reasoning effort."):
    effort = str(reasoning_effort).strip().lower() if reasoning_effort is not None else None
    alias = str(power).strip().lower() if power is not None else None
    if effort == "":
        raise CdxError(usage)
    if alias == "":
        raise CdxError(usage)
    if effort and effort not in REASONING_EFFORT_VALUES:
        raise CdxError(f"Unsupported reasoning effort: {reasoning_effort}")
    if alias and alias not in REASONING_EFFORT_VALUES:
        raise CdxError(f"Unsupported power: {power}")
    if effort and alias and effort != alias:
        raise CdxError("--reasoning-effort and --power must match when both are provided.")
    resolved = effort or alias
    if not resolved:
        return {}
    return {
        "reasoning_effort": resolved,
        "power": resolved,
    }


def _claude_cli_model(model):
    if not model:
        return model
    raw = str(model).strip()
    normalized = raw.lower().replace("_", "-")
    if normalized in CLAUDE_CLI_MODEL_ALIASES:
        return CLAUDE_CLI_MODEL_ALIASES[normalized]

    marketing = re.fullmatch(r"(?:claude-)?(sonnet|opus|haiku)-(\d+)(?:[.-](\d+))?", normalized)
    if marketing:
        family, major, minor = marketing.groups()
        return f"claude-{family}-{major}-{minor}" if minor else family

    dated = re.fullmatch(r"(claude-(?:sonnet|opus|haiku)-4(?:-\d+)*)-\d{8}", normalized)
    if dated:
        return dated.group(1)

    return raw


def _conversation_id(session):
    conversation = session.get("conversation") or {}
    identifier = conversation.get("id")
    return identifier if identifier else None


def _claude_fallback_model(value):
    """Normalize each element of the comma-separated fallback list.

    Claude tries the entries in order, so the separator has to survive while
    each name goes through the same aliasing a primary `--model` gets.
    """
    if not value:
        return value
    return ",".join(_claude_cli_model(element) for element in str(value).split(","))


def _format_budget_arg(value):
    """Render a budget without the float artefacts a bare str() would show.

    A stored 5.0 must reach the CLI as `5`, not `5.0`, and 2.50 as `2.5`.
    """
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:g}"


def _extra_args(session):
    """Unvalidated provider arguments, appended after everything cdx maps.

    Last wins in both provider CLIs, so a passthrough value overrides the
    mapped setting it duplicates. That is the useful default - the escape hatch
    would be pointless if `cdx set` always won - but it is why `cdx configs`
    shows the raw string: the override has to be visible somewhere.
    """
    return split_extra_args((session.get("launch") or {}).get("extra_args")) or []


def _launch_config_args(session):
    launch = session.get("launch") or {}
    args = []
    power = _launch_power(session)
    permission = launch.get("permission")
    provider = session["provider"]
    if provider == PROVIDER_CLAUDE:
        if power:
            args += ["--effort", power]
        if permission:
            args += LAUNCH_PERMISSION_ARGS[PROVIDER_CLAUDE].get(permission, [])
        return args
    if provider in (PROVIDER_ANTIGRAVITY, PROVIDER_OLLAMA):
        # Both read their mapping from the shared table rather than inline
        # branches, so the provider-flag health check can verify what they emit
        # instead of a hand-copied restatement of it.
        args += LAUNCH_FEATURE_ARGS.get(provider, [])
        if permission:
            args += LAUNCH_PERMISSION_ARGS[provider].get(permission, [])
        return args
    if power:
        args += ["-c", f'model_reasoning_effort="{power}"']
    args += _codex_fast_config_args(launch)
    if permission:
        args += LAUNCH_PERMISSION_ARGS[PROVIDER_CODEX].get(permission, [])
    return args


def _list_launch_transcript_paths(session, glob_fn=None):
    import glob

    glob_fn = glob_fn or glob.glob
    log_dir = _get_launch_transcript_dir(session)
    if not os.path.isdir(log_dir):
        return []
    paths = set(glob_fn(os.path.join(log_dir, "cdx-session*.log")))
    legacy = _get_launch_transcript_path(session)
    if os.path.exists(legacy):
        paths.add(legacy)
    return sorted(paths)


def _rotate_log_if_needed(log_path):
    try:
        if os.path.getsize(log_path) >= LOG_ROTATE_BYTES:
            open(log_path, "w").close()
    except OSError:
        pass


def _wrap_launch_with_transcript(session, spec, capture_transcript=True, env=None):
    if not capture_transcript:
        return spec
    env = env or os.environ
    script_bin = env.get("CDX_SCRIPT_BIN", "script")
    script_args = env.get("CDX_SCRIPT_ARGS")
    transcript_path = _build_launch_transcript_path(session)
    os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
    _rotate_log_if_needed(transcript_path)
    if script_args:
        args = shlex.split(script_args)
        if "{transcript}" in args:
            args = [transcript_path if arg == "{transcript}" else arg for arg in args]
        else:
            args = args + [transcript_path]
        args = args + [spec["command"]] + spec["args"]
    else:
        args = _default_script_args(transcript_path, spec)
    return {
        "command": script_bin,
        "args": args,
        "options": spec["options"],
        "label": spec["label"],
        "fallback": spec,
        "transcript_path": transcript_path,
    }


def _default_script_args(transcript_path, spec):
    if sys.platform.startswith("linux"):
        # util-linux `script` flushes with -f (lowercase); -F is the BSD/macOS spelling and errors here.
        command = shlex.join([spec["command"]] + spec["args"])
        return ["-q", "-f", "-c", command, transcript_path]
    return ["-q", "-F", transcript_path, spec["command"]] + spec["args"]


def _rtk_enabled(session):
    return (session.get("launch") or {}).get("rtk") is True


def _logics_manager_available(path=None):
    return shutil.which("logics-manager", path=path) is not None


def _logics_enabled(session, env=None):
    launch = session.get("launch") or {}
    if launch.get("logics") is False:
        return False
    if launch.get("logics") is True:
        return True
    env = env or os.environ
    return _logics_manager_available(path=env.get("PATH"))


def _with_launch_preferences(session, initial_prompt=None, env=None):
    if session["provider"] == PROVIDER_OLLAMA:
        return initial_prompt
    prompts = []
    if _rtk_enabled(session):
        prompts.append(RTK_PROMPT)
    if _logics_enabled(session, env=env):
        prompts.append(LOGICS_PROMPT)
    if not prompts:
        return initial_prompt
    if initial_prompt:
        prompts.append(initial_prompt)
    return "\n\n".join(prompts)


def _build_launch_spec(session, cwd=None, env_override=None, initial_prompt=None, capture_transcript=True):
    _validate_initial_prompt(initial_prompt)
    cwd = cwd or os.getcwd()
    env_override = env_override or {}
    env = {**os.environ, **env_override}
    for key, value in _shared_tool_cache_overrides(env).items():
        env.setdefault(key, value)
    env.update(launch_notify_env(session, notifications_enabled(session)))
    initial_prompt = _with_launch_preferences(session, initial_prompt, env=env)
    _validate_initial_prompt(initial_prompt)
    if session["provider"] == PROVIDER_CLAUDE:
        launch = session.get("launch") or {}
        args = ["--name", session["name"]]
        conversation_id = _conversation_id(session)
        if conversation_id:
            args += ["--session-id", conversation_id]
        if launch.get("model"):
            args += ["--model", _claude_cli_model(launch["model"])]
        args += _launch_config_args(session)
        args += _extra_args(session)
        if initial_prompt:
            args.append(initial_prompt)
        auth_home = _get_auth_home(session)
        claude_env = _claude_env(env, auth_home, own_terminal_title=True)
        oauth_token = _read_claude_launch_oauth_token(auth_home)
        if oauth_token:
            claude_env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
        return _wrap_launch_with_transcript(session, {
            "command": "claude",
            "args": args,
            "options": {
                "cwd": cwd,
                "env": claude_env,
            },
            "label": "claude",
        }, capture_transcript=capture_transcript, env=env)
    if session["provider"] == PROVIDER_ANTIGRAVITY:
        args = _launch_config_args(session)
        if initial_prompt:
            args += ["--prompt-interactive", initial_prompt]
        return _wrap_launch_with_transcript(session, {
            "command": "agy",
            "args": args,
            "options": {
                "cwd": cwd,
                "env": {**env, **_antigravity_env_overrides(_get_auth_home(session))},
            },
            "label": "antigravity",
        }, capture_transcript=capture_transcript, env=env)
    if session["provider"] == PROVIDER_OLLAMA:
        launch = session.get("launch") or {}
        model = launch.get("model") or session["name"]
        ollama_env = {**env, "OLLAMA_NOHISTORY": "1"}
        # `--verbose` arrives through _launch_config_args from
        # LAUNCH_FEATURE_ARGS, so the health check and the launch read one
        # table. Placement between the model and the prompt is accepted --
        # verified against ollama 0.32.11, which parsed the arguments and
        # failed only on the model pull.
        args = ["run", model] + _launch_config_args(session)
        if initial_prompt:
            args.append(initial_prompt)
        return _wrap_launch_with_transcript(session, {
            "command": "ollama",
            "args": args,
            "options": {
                "cwd": cwd,
                "env": ollama_env,
            },
            "label": "ollama",
        }, capture_transcript=capture_transcript, env=env)
    launch = session.get("launch") or {}
    args = ["--no-alt-screen", "--cd", cwd]
    if launch.get("model"):
        args += ["--model", launch["model"]]
    args += _launch_config_args(session)
    if initial_prompt:
        args.append(initial_prompt)
    return _wrap_launch_with_transcript(session, {
        "command": "codex",
        "args": args,
        "options": {
            "env": {**env, "CODEX_HOME": _get_auth_home(session)},
        },
        "label": "codex",
    }, capture_transcript=capture_transcript, env=env)


def _conversation_is_resumable(session, provider, conversation_id):
    """Whether the named conversation exists on disk and can be resumed.

    A lookup failure reads as "not found" rather than raising: this decides
    which of two working strategies to use, so it must never be able to fail a
    command outright.
    """
    if not conversation_id:
        return False
    try:
        from .interactive_usage import conversation_transcript

        return bool(conversation_transcript(provider, _get_auth_home(session), conversation_id))
    except (OSError, ImportError):
        return False


def _redacted_resume_command_preview(session, cwd=None):
    capability = get_resume_capability(session, cwd=cwd)
    return capability.get("command_preview")


def get_resume_capability(session, cwd=None):
    """What resuming this session would actually do.

    The stored conversation id is a claim, not a fact: it survives a launch the
    provider never persisted, and cdx then promised a resume that failed with
    the provider's own raw error. The conversation is therefore looked up
    before it is named, and a missing one degrades to the fallback each
    provider already has rather than being offered as supported.
    """
    provider = session.get("provider")
    cwd = cwd or os.getcwd()
    conversation = session.get("conversation") or {}
    conversation_id = _conversation_id(session)
    known = _conversation_is_resumable(session, provider, conversation_id)
    if provider == PROVIDER_CODEX:
        if known:
            return {
                "resumable": True,
                "provider": provider,
                "strategy": "provider_conversation_id",
                "identity": conversation_id,
                "provenance": conversation.get("provenance"),
                "reason": "supported",
                "command_preview": ["codex", "resume", conversation_id, "--cd", cwd],
            }
        return {
            "resumable": True,
            "provider": provider,
            "strategy": "provider_last",
            "identity": None,
            "provenance": None,
            # Codex only reveals a conversation id once a run has written its
            # rollout, so a session that has never run legitimately has none.
            "reason": "conversation_not_found" if conversation_id else "no_recorded_conversation",
            "command_preview": ["codex", "resume", "--last", "--cd", cwd],
        }
    if provider == PROVIDER_CLAUDE:
        if known:
            return {
                "resumable": True,
                "provider": provider,
                "strategy": "provider_conversation_id",
                "identity": conversation_id,
                "provenance": conversation.get("provenance"),
                "reason": "supported",
                "command_preview": ["claude", "--resume", conversation_id],
            }
        return {
            "resumable": True,
            "provider": provider,
            "strategy": "provider_continue",
            "identity": None,
            "provenance": None,
            "reason": "conversation_not_found" if conversation_id else "no_recorded_conversation",
            "command_preview": ["claude", "--continue"],
        }
    return {
        "resumable": False,
        "provider": provider,
        "strategy": "not_supported",
        "reason": "not_supported",
        "command_preview": [],
    }


def _build_resume_spec(session, cwd=None, env_override=None, capture_transcript=True):
    cwd = cwd or os.getcwd()
    env_override = env_override or {}
    env = {**os.environ, **env_override}
    capability = get_resume_capability(session, cwd=cwd)
    if not capability["resumable"]:
        raise CdxError(f"Provider {session.get('provider')} does not support native resume through cdx.")

    resume_prompt = _with_launch_preferences(session, env=env)
    _validate_initial_prompt(resume_prompt)

    if session["provider"] == PROVIDER_CLAUDE:
        launch = session.get("launch") or {}
        # Resuming by id targets the conversation this session actually last
        # opened; --continue only means "the most recent one in this directory",
        # which another session or another cwd can silently change. So the id
        # is preferred -- but only when the capability confirmed the
        # conversation exists, since naming one the provider never wrote just
        # trades a vaguer resume for a failed one.
        args = (
            ["--resume", capability["identity"]]
            if capability["strategy"] == "provider_conversation_id"
            else ["--continue"]
        )
        args += ["--name", session["name"]]
        if launch.get("model"):
            args += ["--model", _claude_cli_model(launch["model"])]
        args += _launch_config_args(session)
        args += _extra_args(session)
        if resume_prompt:
            args.append(resume_prompt)
        auth_home = _get_auth_home(session)
        claude_env = _claude_env(env, auth_home, own_terminal_title=True)
        oauth_token = _read_claude_launch_oauth_token(auth_home)
        if oauth_token:
            claude_env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
        return _wrap_launch_with_transcript(session, {
            "command": "claude",
            "args": args,
            "options": {
                "cwd": cwd,
                "env": claude_env,
            },
            "label": "claude resume",
        }, capture_transcript=capture_transcript, env=env)

    launch = session.get("launch") or {}
    # Same rule as the Claude branch: name the conversation only when the
    # capability confirmed its rollout exists, else fall back to --last.
    args = (
        ["resume", capability["identity"]]
        if capability["strategy"] == "provider_conversation_id"
        else ["resume", "--last"]
    )
    args += ["--cd", cwd]
    if launch.get("model"):
        args += ["--model", launch["model"]]
    args += _launch_config_args(session)
    args += _extra_args(session)
    if resume_prompt:
        args.append(resume_prompt)
    return _wrap_launch_with_transcript(session, {
        "command": "codex",
        "args": args,
        "options": {
            "env": {**env, "CODEX_HOME": _get_auth_home(session)},
        },
        "label": "codex resume",
    }, capture_transcript=capture_transcript, env=env)


def _validate_initial_prompt(initial_prompt):
    if initial_prompt is not None:
        if not isinstance(initial_prompt, str):
            raise CdxError("initial_prompt must be a string.")
        if len(initial_prompt) > 32768:
            raise CdxError("initial_prompt exceeds maximum allowed length.")


def _build_headless_launch_spec(session, cwd=None, env_override=None, initial_prompt=None):
    _validate_initial_prompt(initial_prompt)
    cwd = cwd or os.getcwd()
    env = {**os.environ, **(env_override or {})}
    # Headless runs read the same home, and so the same hooks, as an interactive
    # launch. Their caller already learns of completion from the return value.
    env.update(launch_notify_env(session, enabled=False))
    initial_prompt = _with_launch_preferences(session, initial_prompt, env=env)
    _validate_initial_prompt(initial_prompt)
    launch = session.get("launch") or {}
    power = _launch_power(session)
    permission = launch.get("permission")
    model = launch.get("model")

    if session["provider"] == PROVIDER_CLAUDE:
        args = ["--print", "--output-format", "json", "--name", session["name"]]
        conversation_id = _conversation_id(session)
        if conversation_id:
            args += ["--session-id", conversation_id]
        if model:
            args += ["--model", _claude_cli_model(model)]
        # --max-budget-usd and --fallback-model are --print-only in the claude
        # CLI, so they belong to this spec alone: the interactive and resume
        # specs would be rejected by the provider for carrying them.
        if launch.get("budget") is not None:
            args += ["--max-budget-usd", _format_budget_arg(launch["budget"])]
        if launch.get("fallback_model"):
            args += ["--fallback-model", _claude_fallback_model(launch["fallback_model"])]
        args += _launch_config_args(session)
        args += _extra_args(session)
        if initial_prompt:
            args.append(initial_prompt)
        auth_home = _get_auth_home(session)
        claude_env = _claude_env(env, auth_home)
        oauth_token = _read_claude_launch_oauth_token(auth_home)
        if oauth_token:
            claude_env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
        return {
            "command": "claude",
            "args": args,
            "options": {"cwd": cwd, "env": claude_env},
            "label": "claude",
            "sensitive_args": [initial_prompt] if initial_prompt else [],
        }

    if session["provider"] == PROVIDER_CODEX:
        args = ["exec", "--json", "-C", cwd]
        if model:
            args += ["--model", model]
        if power:
            args += ["-c", f'model_reasoning_effort="{power}"']
        args += _codex_fast_config_args(launch)
        if permission:
            args += HEADLESS_CODEX_PERMISSION_ARGS.get(permission, [])
        if initial_prompt:
            args.append(initial_prompt)
        return {
            "command": "codex",
            "args": args,
            "options": {"cwd": cwd, "env": {**env, "CODEX_HOME": _get_auth_home(session)}},
            "label": "codex",
            "sensitive_args": [initial_prompt] if initial_prompt else [],
        }

    return _build_launch_spec(
        session,
        cwd=cwd,
        env_override=env_override,
        initial_prompt=initial_prompt,
        capture_transcript=False,
    )


def _headless_artifact_paths(session, run_id=None):
    run_id = run_id or uuid.uuid4().hex
    log_dir = _get_launch_transcript_dir(session)
    os.makedirs(log_dir, exist_ok=True)
    prefix = os.path.join(log_dir, f"cdx-run-{run_id}")
    return {
        "run_id": run_id,
        "transcript_path": os.path.abspath(f"{prefix}.log"),
        "stdout_path": os.path.abspath(f"{prefix}.stdout.log"),
        "stderr_path": os.path.abspath(f"{prefix}.stderr.log"),
    }


def _combine_headless_transcript(paths):
    transcript_path = paths["transcript_path"]
    with open(transcript_path, "w", encoding="utf-8", errors="replace") as transcript:
        for label, path_key in (("stdout", "stdout_path"), ("stderr", "stderr_path")):
            path = paths.get(path_key)
            if not path:
                continue
            transcript.write(f"--- {label} ---\n")
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    content = handle.read()
            except OSError:
                content = ""
            transcript.write(content)
            if content and not content.endswith("\n"):
                transcript.write("\n")


def _headless_run_info(paths, spec, start_time, returncode):
    end_time = datetime.now(timezone.utc)
    return {
        **paths,
        "started_at": start_time.isoformat().replace("+00:00", "Z"),
        "ended_at": end_time.isoformat().replace("+00:00", "Z"),
        "duration_ms": int((end_time - start_time).total_seconds() * 1000),
        "command": spec.get("command"),
        "args": _redact_sensitive_args(spec),
        "label": spec.get("label"),
        "pid": None,
        "returncode": returncode,
        "timed_out": False,
    }


def _redact_sensitive_args(spec):
    args = list(spec.get("args") or [])
    sensitive = {value for value in (spec.get("sensitive_args") or []) if value}
    if not sensitive:
        return args
    return [REDACTED_PROMPT_ARG if arg in sensitive else arg for arg in args]


def _signal_child_group(child, sig):
    # Providers spawn helpers of their own; signal the whole group so
    # grandchildren die with the child. Falls back to False when the child
    # shares our group (test doubles spawned without start_new_session).
    pid = getattr(child, "pid", None)
    if not pid or not hasattr(os, "getpgid"):
        return False
    try:
        pgid = os.getpgid(pid)
        if pgid == os.getpgid(0):
            return False
        os.killpg(pgid, sig)
        return True
    except (OSError, TypeError):
        return False


def _terminate_child_tree(child):
    if not _signal_child_group(child, signal.SIGTERM):
        try:
            child.terminate()
        except Exception:
            pass
    try:
        child.wait(timeout=5)
        return
    except Exception:
        pass
    if not _signal_child_group(child, signal.SIGKILL):
        try:
            child.kill()
        except Exception:
            pass
    try:
        child.wait()
    except Exception:
        pass


def _run_headless_provider_command(session, cwd=None, env_override=None, initial_prompt=None,
                                   timeout_seconds=None, spawn=None, run_id=None):
    spawn = spawn or subprocess.Popen
    spec = _build_headless_launch_spec(
        session,
        cwd=cwd,
        env_override=env_override,
        initial_prompt=initial_prompt,
    )
    paths = _headless_artifact_paths(session, run_id=run_id)
    start_time = datetime.now(timezone.utc)
    command = spec["command"]
    if spawn is subprocess.Popen:
        command = _resolve_command(command, spec.get("options", {}).get("env"))

    child = None
    timed_out = False
    with open(paths["stdout_path"], "w", encoding="utf-8", errors="replace") as stdout_file, \
            open(paths["stderr_path"], "w", encoding="utf-8", errors="replace") as stderr_file:
        options = {k: v for k, v in spec.get("options", {}).items() if k not in ("stdio", "stdout", "stderr")}
        if spawn is subprocess.Popen:
            # Own process group so a timeout can kill grandchildren too.
            options["start_new_session"] = True
        try:
            child = spawn(
                [command] + spec["args"],
                stdout=stdout_file,
                stderr=stderr_file,
                **options,
            )
        except FileNotFoundError as error:
            _combine_headless_transcript(paths)
            cdx_error = CdxError(f"{spec['label']} CLI not found on PATH: {spec['command']}", 127)
            cdx_error.run_info = _headless_run_info(paths, spec, start_time, 127)
            raise cdx_error from error
        except OSError as error:
            _combine_headless_transcript(paths)
            cdx_error = CdxError(f"Failed to start {spec['label']}: {error}", 126)
            cdx_error.run_info = _headless_run_info(paths, spec, start_time, 126)
            raise cdx_error from error
        try:
            if timeout_seconds is None:
                child.wait()
            else:
                child.wait(timeout=timeout_seconds)
        except TypeError:
            child.wait()
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_child_tree(child)

    _combine_headless_transcript(paths)
    end_time = datetime.now(timezone.utc)
    returncode = getattr(child, "returncode", None) if child is not None else None
    if timed_out and (returncode is None or returncode == 0):
        returncode = 124
    return {
        **paths,
        "started_at": start_time.isoformat().replace("+00:00", "Z"),
        "ended_at": end_time.isoformat().replace("+00:00", "Z"),
        "duration_ms": int((end_time - start_time).total_seconds() * 1000),
        "command": spec.get("command"),
        "args": _redact_sensitive_args(spec),
        "label": spec.get("label"),
        "pid": getattr(child, "pid", None),
        "returncode": returncode,
        "timed_out": timed_out,
    }


def _build_login_status_spec(session, env_override=None):
    env = {**os.environ, **(env_override or {})}
    if session["provider"] == PROVIDER_CLAUDE:
        auth_home = _get_auth_home(session)
        env = _claude_env(env, auth_home)
        oauth_token = _read_claude_launch_oauth_token(auth_home)
        if oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

        def parser(output):
            try:
                return bool(json.loads(output or "{}").get("loggedIn"))
            except (json.JSONDecodeError, AttributeError):
                return False

        return {"command": "claude", "args": ["auth", "status"], "env": env,
                "parser": parser, "label": "claude auth status"}
    if session["provider"] == PROVIDER_ANTIGRAVITY:
        env.update(_antigravity_env_overrides(_get_auth_home(session)))
        return {"command": "agy", "args": ["--version"], "env": env,
                "parser": lambda _output: True, "label": "antigravity cli"}
    if session["provider"] == PROVIDER_OLLAMA:
        return {"command": "ollama", "args": ["--version"], "env": {**env, "OLLAMA_NOHISTORY": "1"},
                "parser": lambda _output: True, "label": "ollama cli"}
    env["CODEX_HOME"] = _get_auth_home(session)

    def parser(output):
        if "Not logged in" in (output or ""):
            return False
        return "Logged in" in (output or "")

    return {"command": "codex", "args": ["login", "status"], "env": env,
            "parser": parser, "label": "codex login status"}


def _build_auth_action_spec(session, action, cwd=None, env_override=None):
    cwd = cwd or os.getcwd()
    env = {**os.environ, **(env_override or {})}
    if session["provider"] == PROVIDER_CLAUDE:
        auth_home = _get_auth_home(session)
        env = _claude_env(env, auth_home)
        args = ["auth", action]
        label = f"claude auth {action}"
        if action == "setup-token":
            spec = {"command": "claude", "args": ["setup-token"],
                    "options": {"cwd": cwd, "env": env}, "label": "claude setup-token"}
            return _wrap_launch_with_transcript(session, spec, env=env)
        if action == "login":
            email = _read_claude_account_email(auth_home)
            if email:
                args += ["--email", email]
        return {"command": "claude", "args": args,
                "options": {"cwd": cwd, "env": env}, "label": label}
    if session["provider"] == PROVIDER_ANTIGRAVITY:
        if action == "logout":
            raise CdxError("Antigravity logout is managed inside agy. Launch the session and run /logout.")
        env.update(_antigravity_env_overrides(_get_auth_home(session)))
        return {"command": "agy", "args": [],
                "options": {"cwd": cwd, "env": env}, "label": "antigravity"}
    if session["provider"] == PROVIDER_OLLAMA:
        if action == "logout":
            raise CdxError("Ollama sessions do not use cdx-managed authentication.")
        return {"command": "ollama", "args": ["list"],
                "options": {"cwd": cwd, "env": {**env, "OLLAMA_NOHISTORY": "1"}}, "label": "ollama"}
    env["CODEX_HOME"] = _get_auth_home(session)
    return {"command": "codex", "args": [action],
            "options": {"cwd": cwd, "env": env}, "label": f"codex {action}"}


def _format_probe_failure(session, spec, error):
    command = spec["command"]
    if isinstance(error, FileNotFoundError):
        return CdxError(
            f"Failed to check login status for {session['name']}: {command} CLI not found on PATH. "
            f"Install {command} and retry cdx add {session['name']}.",
            127,
        )
    if isinstance(error, OSError) and error.errno == errno.ENOEXEC:
        target = getattr(error, "filename", None) or command
        return CdxError(
            f"Failed to check login status for {session['name']}: {target} is not a valid executable "
            f"(corrupted install, wrong architecture, or a script missing its shebang). "
            f"Reinstall {command} and retry.",
            126,
        )
    message = getattr(error, "message", None) or str(error)
    return CdxError(f"Failed to check login status for {session['name']}: {message}")


def _resolve_command(command, env=None):
    env = env or os.environ
    return shutil.which(command, path=env.get("PATH")) or command


def _auth_probe_degraded_message(session):
    return (
        f"Auth probe timed out after {AUTH_PROBE_TIMEOUT_SECONDS}s for session {session.get('name') or 'unknown'}; "
        "authentication status is degraded."
    )


def _probe_provider_auth_status(session, spawn_sync=None, env_override=None, trust_local_credentials=True):
    spawn_sync = spawn_sync or subprocess.run
    spec = _build_login_status_spec(session, env_override)
    if trust_local_credentials:
        if session.get("provider") == PROVIDER_CLAUDE and _has_local_claude_auth(_get_auth_home(session)):
            return AUTH_PROBE_AUTHENTICATED
        if session.get("provider") == PROVIDER_CODEX and _has_local_codex_auth(_get_auth_home(session)):
            return AUTH_PROBE_AUTHENTICATED
    try:
        if spawn_sync is subprocess.run:
            command = _resolve_command(spec["command"], spec["env"])
            result = subprocess.run(
                [command] + spec["args"],
                env=spec["env"],
                capture_output=True, text=True,
                timeout=AUTH_PROBE_TIMEOUT_SECONDS,
            )
            output = (result.stdout or "") + (result.stderr or "")
        else:
            result = spawn_sync(spec["command"], spec["args"], spec)
            error = result.get("error") if isinstance(result, dict) else getattr(result, "error", None)
            if error:
                if isinstance(error, subprocess.TimeoutExpired):
                    raise error
                raise _format_probe_failure(session, spec, error)
            stdout = result.get("stdout") if isinstance(result, dict) else getattr(result, "stdout", "")
            stderr = result.get("stderr") if isinstance(result, dict) else getattr(result, "stderr", "")
            output = (stdout or "") + (stderr or "")
    except subprocess.TimeoutExpired:
        return AUTH_PROBE_DEGRADED
    except OSError as error:
        raise _format_probe_failure(session, spec, error) from error
    return AUTH_PROBE_AUTHENTICATED if spec["parser"](output) else AUTH_PROBE_LOGGED_OUT


def _probe_provider_auth(session, spawn_sync=None, env_override=None, trust_local_credentials=True):
    return _probe_provider_auth_status(
        session,
        spawn_sync=spawn_sync,
        env_override=env_override,
        trust_local_credentials=trust_local_credentials,
    ) == AUTH_PROBE_AUTHENTICATED


_SIGNAL_EXIT_CODES = {signal.SIGINT: 130, signal.SIGTERM: 143}
if hasattr(signal, "SIGHUP"):
    _SIGNAL_EXIT_CODES[signal.SIGHUP] = 129

# The exit codes above, on their own: what a caller checks to tell "the user
# killed this session" apart from "the provider process crashed on its own".
INTERRUPT_EXIT_CODES = frozenset(_SIGNAL_EXIT_CODES.values())


def _signal_exit_code(sig):
    return _SIGNAL_EXIT_CODES.get(sig, 1)


def _signal_name(sig):
    if hasattr(sig, "name"):
        return sig.name
    try:
        return signal.Signals(sig).name
    except (TypeError, ValueError):
        return str(sig)


def _sanitize_terminal_title_component(value):
    """Strip anything that could escape the OSC title string.

    Session names and directories are user data, so they are the injection
    vector here: a raw ESC or BEL inside either would end the title string and
    let the rest be read as terminal commands.
    """
    if value is None:
        return ""
    return _TERMINAL_TITLE_CONTROL_CHARS.sub("", str(value)).strip()


def format_terminal_title(session_name, cwd=None):
    """Build the `session -- folder` title shared by every interactive provider.

    The folder is the basename of the effective launch cwd, which is what
    identifies the work; the full path would not fit a title bar. Missing parts
    are dropped rather than rendered as an empty half.
    """
    session_part = _sanitize_terminal_title_component(session_name)
    directory = os.path.abspath(cwd or os.getcwd())
    folder_part = _sanitize_terminal_title_component(os.path.basename(directory) or directory)
    parts = [part for part in (session_part, folder_part) if part]
    return TERMINAL_TITLE_SEPARATOR.join(parts)


def _stream_is_tty(stream):
    try:
        return bool(stream is not None and stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


class _TerminalTitleKeeper:
    """Holds the terminal title for as long as the provider process runs.

    A provider TUI sets its own title whenever it repaints, so this rewrites the
    OSC sequence on an interval instead of once. Every write is best-effort: a
    closed or unwritable stream ends the loop rather than the session.
    """

    def __init__(self, title, stream, interval=None):
        self.title = title
        self._sequence = f"\033]0;{title}\007"
        self._stream = stream
        self._interval = TERMINAL_TITLE_REFRESH_SECONDS if interval is None else interval
        self._stop_event = threading.Event()
        self._thread = None

    def _write(self):
        try:
            self._stream.write(self._sequence)
            self._stream.flush()
        except Exception:
            return False
        return True

    def start(self):
        if not self._write():
            return self
        if self._interval and self._interval > 0:
            self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
            self._thread.start()
        return self

    def _refresh_loop(self):
        while not self._stop_event.wait(self._interval):
            if not self._write():
                return

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)


def _start_terminal_title(session, action, cwd=None, stream=None, enabled=True):
    """Start title upkeep for an interactive launch/resume, or return None.

    Returns None for every case that has no terminal to write to - auth
    actions, non-TTY stdout, JSON output, captured test streams - so callers can
    stop() unconditionally.
    """
    if not enabled or action not in TERMINAL_TITLE_ACTIONS:
        return None
    if session.get("provider") not in TERMINAL_TITLE_PROVIDERS:
        return None
    stream = sys.stdout if stream is None else stream
    if not _stream_is_tty(stream):
        return None
    title = format_terminal_title(session.get("name"), cwd)
    if not title:
        return None
    return _TerminalTitleKeeper(title, stream).start()


def _run_interactive_provider_command(session, action, spawn=None, cwd=None,
                                      env_override=None, signal_emitter=None,
                                      initial_prompt=None, lifecycle_callback=None,
                                      title_stream=None, title_enabled=True):
    kwargs = dict(spawn=spawn, cwd=cwd, env_override=env_override,
                  signal_emitter=signal_emitter, initial_prompt=initial_prompt,
                  lifecycle_callback=lifecycle_callback, title_stream=title_stream,
                  title_enabled=title_enabled)
    if session.get("provider") != PROVIDER_CODEX:
        return _run_interactive_provider_command_impl(session, action, **kwargs)
    # Hold the per-CODEX_HOME lock for the whole session so concurrent Codex
    # processes cannot rotate the refresh_token under each other.
    with codex_auth_lock(
        _get_auth_home(session),
        blocking=True,
        timeout_seconds=CODEX_INTERACTIVE_AUTH_LOCK_TIMEOUT_SECONDS,
    ) as acquired:
        if not acquired:
            raise CdxError(f"Timed out waiting for Codex auth lock for session {session['name']}.")
        return _run_interactive_provider_command_impl(session, action, **kwargs)


def _run_interactive_provider_command_impl(session, action, spawn=None, cwd=None,
                                           env_override=None, signal_emitter=None,
                                           initial_prompt=None, lifecycle_callback=None,
                                           title_stream=None, title_enabled=True):
    # The title lives exactly as long as the provider process, including the
    # error and signal paths below, which is why it is held here rather than
    # inside the run itself.
    title_keeper = _start_terminal_title(
        session, action, cwd=cwd, stream=title_stream, enabled=title_enabled
    )
    try:
        return _run_interactive_provider_process(
            session, action, spawn=spawn, cwd=cwd, env_override=env_override,
            signal_emitter=signal_emitter, initial_prompt=initial_prompt,
            lifecycle_callback=lifecycle_callback,
        )
    finally:
        if title_keeper is not None:
            title_keeper.stop()


def _run_interactive_provider_process(session, action, spawn=None, cwd=None,
                                      env_override=None, signal_emitter=None,
                                      initial_prompt=None, lifecycle_callback=None):
    spawn = spawn or subprocess.Popen
    if action == "launch":
        spec = _build_launch_spec(session, cwd=cwd, env_override=env_override, initial_prompt=initial_prompt)
    elif action == "resume":
        if initial_prompt is not None:
            raise CdxError("initial_prompt is not supported for resume.")
        spec = _build_resume_spec(session, cwd=cwd, env_override=env_override)
    else:
        spec = _build_auth_action_spec(session, action, cwd=cwd, env_override=env_override)
    def start_child(current_spec):
        command = current_spec["command"]
        if spawn is subprocess.Popen:
            command = _resolve_command(command, current_spec.get("options", {}).get("env"))
        return spawn(
            [command] + current_spec["args"],
            **{k: v for k, v in current_spec.get("options", {}).items() if k != "stdio"},
        )

    start_time = datetime.now(timezone.utc)

    child_pid = None

    def run_info(current_spec, returncode=None):
        end_time = datetime.now(timezone.utc)
        return {
            "started_at": start_time.isoformat().replace("+00:00", "Z"),
            "ended_at": end_time.isoformat().replace("+00:00", "Z"),
            "duration_ms": int((end_time - start_time).total_seconds() * 1000),
            "command": current_spec.get("command"),
            "args": list(current_spec.get("args") or []),
            "label": current_spec.get("label"),
            "transcript_path": current_spec.get("transcript_path"),
            "pid": child_pid,
            "returncode": returncode,
        }

    try:
        child = start_child(spec)
    except FileNotFoundError as error:
        spec = _fallback_launch_spec_or_raise(spec, error)
        child = start_child(spec)
    child_pid = getattr(child, "pid", None) or os.getpid()
    if lifecycle_callback:
        lifecycle_callback("started", run_info(spec))

    forwarded_signal = None
    handlers = []

    def forward(sig, _frame=None):
        nonlocal forwarded_signal
        forwarded_signal = sig
        try:
            if hasattr(child, "send_signal"):
                child.send_signal(sig)
            elif hasattr(child, "kill"):
                child.kill(sig)
        except Exception:
            pass

    original_handlers = {}
    use_emitter = hasattr(signal_emitter, "on") and hasattr(signal_emitter, "removeListener")

    if use_emitter:
        for sig in ("SIGINT", "SIGTERM", "SIGHUP"):
            handler = lambda current_sig=sig: forward(getattr(signal, current_sig), None)
            handlers.append((sig, handler))
            signal_emitter.on(sig, handler)
    else:
        _forward_sigs = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGHUP"):
            _forward_sigs.append(signal.SIGHUP)
        for sig in _forward_sigs:
            try:
                original_handlers[sig] = signal.signal(sig, forward)
            except (OSError, ValueError):
                pass

    try:
        child.wait()
        if forwarded_signal is None and child.returncode != 0 and _should_retry_without_transcript(spec):
            spec = _fallback_launch_spec_or_raise(spec)
            child = start_child(spec)
            child_pid = getattr(child, "pid", None) or os.getpid()
            if lifecycle_callback:
                lifecycle_callback("started", run_info(spec))
            child.wait()
    finally:
        if use_emitter:
            for sig, handler in handlers:
                try:
                    signal_emitter.removeListener(sig, handler)
                except Exception:
                    pass
        else:
            for sig, handler in original_handlers.items():
                try:
                    signal.signal(sig, handler)
                except (OSError, ValueError):
                    pass

    if forwarded_signal is not None:
        error = CdxError(
            f"{spec['label']} interrupted by {_signal_name(forwarded_signal)} for session {session['name']}",
            _signal_exit_code(forwarded_signal),
        )
        error.run_info = run_info(spec, returncode=error.exit_code)
        if lifecycle_callback:
            lifecycle_callback("finished", error.run_info)
        raise error
    if child.returncode != 0:
        error = CdxError(
            f"{spec['label']} exited with code {child.returncode} for session {session['name']}"
        )
        error.run_info = run_info(spec, returncode=child.returncode)
        if lifecycle_callback:
            lifecycle_callback("finished", error.run_info)
        raise error
    info = run_info(spec, returncode=child.returncode)
    if lifecycle_callback:
        lifecycle_callback("finished", info)
    return info


def _fallback_launch_spec_or_raise(spec, original_error=None):
    fallback = spec.get("fallback")
    if not fallback:
        if original_error is not None:
            raise original_error
        raise CdxError(f"{spec['label']} cannot run without a fallback")
    return {**fallback, "label": f"{fallback['label']} (without transcript)"}


def _should_retry_without_transcript(spec):
    if not spec.get("fallback"):
        return False
    transcript_path = spec.get("transcript_path")
    if not transcript_path:
        return False
    try:
        return not os.path.exists(transcript_path) or os.path.getsize(transcript_path) == 0
    except OSError:
        return True


def _ensure_session_authentication(session, service, spawn=None, spawn_sync=None,
                                   stdin_is_tty=True, env_override=None, behavior="launch",
                                   signal_emitter=None, trust_local_credentials=True):
    if behavior == "launch" and (session.get("auth") or {}).get("status") == "logged_out":
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    auth_status = _probe_provider_auth_status(
        session,
        spawn_sync=spawn_sync,
        env_override=env_override,
        trust_local_credentials=trust_local_credentials,
    )
    if auth_status == AUTH_PROBE_AUTHENTICATED:
        return {"authenticated": True, "checked": True, "status": auth_status}
    if auth_status == AUTH_PROBE_DEGRADED:
        result = {
            "authenticated": False,
            "checked": True,
            "status": auth_status,
            "error": _auth_probe_degraded_message(session),
        }
        if behavior == "probe-only":
            return result
        raise CdxError(f"{result['error']} Retry, or run: cdx login {session['name']}")
    if behavior == "probe-only":
        return {"authenticated": False, "checked": True, "status": auth_status}
    if behavior == "launch":
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    if not stdin_is_tty:
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    _run_interactive_provider_command(
        session, "login", spawn=spawn, env_override=env_override, signal_emitter=signal_emitter
    )
    return {"authenticated": True, "checked": True, "bootstrapped": True}
