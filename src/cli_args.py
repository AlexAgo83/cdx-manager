#!/usr/bin/env python3
"""Argument parsers and usage strings for cdx commands.

Split out of cli_commands.py: pure input-parsing layer (no command execution),
imported back there and used by the handlers.
"""

from datetime import datetime, timedelta

from .config import (
    MAX_LAUNCH_BUDGET_USD,
    PERMISSION_ALIASES,
    PERMISSION_INPUT_VALUES,
    PERMISSION_VALUES,
    PROVIDER_CODEX,
    PROVIDERS,
    REASONING_EFFORT_VALUES,
    normalize_permission,
)
from .errors import CdxArgumentError, CdxError
from .provider_runtime import _normalize_reasoning_effort

STATUS_USAGE = "Usage: cdx status [--json] [--refresh|--cached] [--timeout SECONDS] | cdx status --small|-s [--refresh|--cached] [--timeout SECONDS] | cdx status <name> [--json] [--refresh|--cached] [--timeout SECONDS]"
DOCTOR_USAGE = "Usage: cdx doctor [--severity OK|WARN|FAIL[,OK|WARN|FAIL...]] [--check-provider-flags] [--json]"
DISK_USAGE = "Usage: cdx disk [profiles] [--candidates] [--json]"
REPAIR_USAGE = "Usage: cdx repair [--dry-run] [--force] [--json]"
UPDATE_USAGE = "Usage: cdx update [all] [--check] [--yes] [--json] [--version TAG]"
EXPORT_USAGE = "Usage: cdx export <file> [--include-auth] [--force] [--json] [--sessions name1,name2] [--passphrase-env VAR|--passphrase-stdin]"
IMPORT_USAGE = "Usage: cdx import <file> [--force|--merge] [--allow-authless-force] [--json] [--sessions name1,name2] [--passphrase-env VAR|--passphrase-stdin]"
CONTEXT_USAGE = "Usage: cdx context show|path|init|edit|clear|set|append [text...] [--json]"
MEMORY_USAGE = "Usage: cdx memory [--global|--project NAME_OR_PATH] [show|view|path|init|edit|clear|set|append|list] [text...] [--json]"
HANDOFF_USAGE = "Usage: cdx handoff <name> [--json] | cdx handoff <source> <target> [--json]"
LABEL_USAGE = "Usage: cdx label <name> <label> [--json] | cdx label <name> --clear [--json]"
SET_USAGE = "Usage: cdx set <name>|--sessions all|a,b|--provider PROVIDER [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full] [--fast on|off] [--rtk on|off] [--logics on|off] [--model MODEL] [--fallback-model MODEL[,MODEL...]] [--budget USD] [--priority 0..100] [--json]"
UNSET_USAGE = "Usage: cdx unset <name>|--sessions all|a,b|--provider PROVIDER (--power|--reasoning-effort|--permission|--fast|--rtk|--logics|--model|--fallback-model|--budget|--priority|--all) [--json]"
SETTING_ALIAS_USAGE = "Usage: cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b> <value|default> [--json]"
CONFIG_USAGE = "Usage: cdx config <name> [--json]"
CONFIGS_USAGE = "Usage: cdx configs [--json]"
HISTORY_USAGE = "Usage: cdx history [name] [--limit N] [--summary] [--since 7d|today|DATE] [--from DATE] [--to DATE] [--json]"
STATS_USAGE = "Usage: cdx stats [name] [--since 7d|today|DATE] [--from DATE] [--to DATE] [--json]"
LAST_USAGE = "Usage: cdx last [--json]"
RESUME_USAGE = "Usage: cdx resume <name> [--json]"
CAN_RESUME_USAGE = "Usage: cdx can-resume <name> [--json]"
SELECT_USAGE = "Usage: cdx select --provider PROVIDER [--min-reasoning-effort minimal|low|medium|high|xhigh] [--min-power minimal|low|medium|high|xhigh] [--require-ready] [--refresh] --json"
NEXT_USAGE = "Usage: cdx next [--json] [--refresh]"
RUN_USAGE = "Usage: cdx run [session] --cwd PATH (--prompt-file PATH|--prompt TEXT|--prompt-file -) [--provider PROVIDER] [--model MODEL] [--kind assistant|code-review] [--reasoning-effort minimal|low|medium|high|xhigh] [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full|workspace-write|read-only|danger-full-access] [--timeout-seconds N] [--detach] [--failover] [--refresh] --json"
RUN_JSON_REQUIRED = "cdx run: --json is required."
RUN_TARGET_REQUIRED = "cdx run: specify a session name or --provider PROVIDER."
RUN_SESSION_PROVIDER_CONFLICT = "cdx run: cannot specify both a session name and --provider."
RUN_CWD_REQUIRED = "cdx run: --cwd PATH is required."
RUN_PROMPT_SOURCE_REQUIRED = "cdx run: specify exactly one prompt source: --prompt TEXT or --prompt-file PATH."
RUN_DETACH_FAILOVER_CONFLICT = "cdx run: --failover needs to watch the run, which --detach gives up."
RUN_KIND_VALUES = ("assistant", "code-review")
# Aliases of the shared definitions in config, kept only so the existing
# RUN_* spellings in this module keep reading naturally. They are references,
# not copies: config.py is the single owner.
RUN_PERMISSION_VALUES = PERMISSION_INPUT_VALUES
RUN_PERMISSION_CANONICAL_VALUES = PERMISSION_VALUES
RUN_PERMISSION_ALIASES = PERMISSION_ALIASES
RUN_EFFORT_VALUES = REASONING_EFFORT_VALUES
RUNS_USAGE = "Usage: cdx runs [--limit N] [--since 7d|today|DATE] --json"
RUN_STATUS_USAGE = "Usage: cdx run-status <run_id> --json"
RUN_REPORT_USAGE = "Usage: cdx run-report <run_id> --json"
RUN_TAIL_USAGE = "Usage: cdx run-tail <run_id> [--lines N] --json"
SCHEMA_USAGE = "Usage: cdx schema --json"

RUN_TAIL_DEFAULT_LINES = 50
RUN_TAIL_MAX_LINES = 2000

# Argument-failure codes emitted in `error.code`. Specific enough that a caller
# branches on the code alone, never on the human message.
ARG_CODE_MISSING = "missing_required_argument"
ARG_CODE_MUTUALLY_EXCLUSIVE = "mutually_exclusive_arguments"
ARG_CODE_INVALID_VALUE = "invalid_argument_value"
ARG_CODE_OUT_OF_RANGE = "argument_value_out_of_range"
ARG_CODE_UNKNOWN = "unknown_argument"


def _parse_json_flag(args):
    json_flag = "--json" in args
    cleaned = [arg for arg in args if arg != "--json"]
    return json_flag, cleaned


def _parse_doctor_args(args):
    parsed = {"json": False, "severity": None, "check_provider_flags": False}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--json":
            parsed["json"] = True
            index += 1
            continue
        if arg == "--check-provider-flags":
            parsed["check_provider_flags"] = True
            index += 1
            continue
        if arg == "--severity":
            if parsed["severity"] is not None or index + 1 >= len(args):
                raise CdxError(DOCTOR_USAGE)
            value = args[index + 1]
            index += 2
        elif arg.startswith("--severity="):
            if parsed["severity"] is not None:
                raise CdxError(DOCTOR_USAGE)
            value = arg.split("=", 1)[1]
            index += 1
        else:
            raise CdxError(DOCTOR_USAGE)

        values = [item.strip().upper() for item in value.split(",")]
        if not values or any(item not in {"OK", "WARN", "FAIL"} for item in values):
            raise CdxError(DOCTOR_USAGE)
        parsed["severity"] = ",".join(dict.fromkeys(values))
    return parsed


def _parse_flag_args(args, schema, usage, positionals_key=None, max_positionals=0):
    parsed = {spec["key"]: spec.get("default") for spec in schema.values()}
    positionals = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in schema:
            spec = schema[arg]
            if spec["type"] == "bool":
                parsed[spec["key"]] = True
                index += 1
                continue
            value, index = _read_option_value(args, index, usage, schema=schema)
            parsed[spec["key"]] = spec.get("transform", lambda item: item)(value)
            continue
        if arg.startswith("--") and "=" in arg:
            flag, value = arg.split("=", 1)
            spec = schema.get(flag)
            if not spec or spec["type"] == "bool":
                raise CdxError(usage)
            parsed[spec["key"]] = spec.get("transform", lambda item: item)(value)
            index += 1
            continue
        if arg.startswith("-"):
            raise CdxError(usage)
        positionals.append(arg)
        if len(positionals) > max_positionals:
            raise CdxError(usage)
        index += 1

    if positionals_key is not None:
        parsed[positionals_key] = positionals
    return parsed


def _parse_add_args(args):
    parsed = _parse_flag_args(
        args,
        {"--model": {"key": "model", "type": "str", "default": None}},
        "Usage: cdx add [provider] <name> [--model MODEL] [--json]",
        positionals_key="values",
        max_positionals=2,
    )
    values = parsed["values"]
    if len(values) == 1:
        return {"provider": PROVIDER_CODEX, "name": values[0], "model": parsed["model"]}
    if len(values) == 2:
        return {"provider": values[0], "name": values[1], "model": parsed["model"]}
    raise CdxError("Usage: cdx add [provider] <name> [--model MODEL] [--json]")


def _parse_copy_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx cp <source> <dest> [--json]")
    return {"source": args[0], "dest": args[1]}


def _parse_rename_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx ren <source> <dest> [--json]")
    return {"source": args[0], "dest": args[1]}


def _parse_label_args(args):
    parsed = _parse_flag_args(args, {
        "--clear": {"key": "clear", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, LABEL_USAGE, positionals_key="values", max_positionals=2)
    values = parsed["values"]
    if parsed["clear"]:
        if len(values) != 1:
            raise CdxError(LABEL_USAGE)
        return {"name": values[0], "label": None, "clear": True, "json": parsed["json"]}
    if len(values) != 2:
        raise CdxError(LABEL_USAGE)
    return {"name": values[0], "label": values[1], "clear": False, "json": parsed["json"]}


def _parse_remove_args(args):
    parsed = _parse_flag_args(args, {
        "--force": {"key": "force", "type": "bool", "default": False},
    }, "Usage: cdx rmv <name> [--force] [--json]", positionals_key="names", max_positionals=1)
    if len(parsed["names"]) != 1:
        raise CdxError("Usage: cdx rmv <name> [--force] [--json]")
    return {"name": parsed["names"][0], "force": parsed["force"]}


def _parse_toggle_args(args, usage):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, usage, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) != 1:
        raise CdxError(usage)
    return {"name": parsed["names"][0], "json": parsed["json"]}


def _parse_fast_value(value):
    text = str(value).strip().lower()
    if text in ("on", "true", "1", "yes"):
        return True
    if text in ("off", "false", "0", "no"):
        return False
    raise CdxError(SET_USAGE)


def _parse_priority_value(value):
    try:
        priority = int(value)
    except (TypeError, ValueError) as error:
        raise CdxError(SET_USAGE) from error
    if priority < 0 or priority > 100:
        raise CdxError(SET_USAGE)
    return priority


def _parse_budget_value(value):
    try:
        budget = float(value)
    except (TypeError, ValueError) as error:
        raise CdxError(SET_USAGE) from error
    # NaN compares false against every bound, so reject it before the range check.
    if budget != budget or budget <= 0 or budget > MAX_LAUNCH_BUDGET_USD:
        raise CdxError(SET_USAGE)
    return budget


def _parse_set_args(args):
    parsed = _parse_flag_args(args, {
        "--power": {"key": "power", "type": "str", "default": None},
        "--permission": {"key": "permission", "type": "str", "default": None},
        "--fast": {"key": "fast", "type": "str", "default": None, "transform": _parse_fast_value},
        "--rtk": {"key": "rtk", "type": "str", "default": None, "transform": _parse_fast_value},
        "--logics": {"key": "logics", "type": "str", "default": None, "transform": _parse_fast_value},
        "--model": {"key": "model", "type": "str", "default": None},
        "--fallback-model": {"key": "fallback_model", "type": "str", "default": None},
        "--budget": {"key": "budget", "type": "str", "default": None, "transform": _parse_budget_value},
        "--priority": {"key": "priority", "type": "str", "default": None, "transform": _parse_priority_value},
        "--sessions": {"key": "sessions", "type": "str", "default": None, "transform": _parse_set_unset_sessions},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, SET_USAGE)},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, SET_USAGE, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) > 1:
        raise CdxError(SET_USAGE)
    if parsed["names"] and parsed["sessions"]:
        raise CdxError(SET_USAGE)
    if parsed["names"] and parsed["provider"]:
        raise CdxError(SET_USAGE)
    if parsed["sessions"] and parsed["provider"]:
        raise CdxError(SET_USAGE)
    if not parsed["names"] and not parsed["sessions"] and not parsed["provider"]:
        raise CdxError(SET_USAGE)
    settings = {
        key: parsed[key]
        for key in ("power", "permission", "fast", "rtk", "logics", "model", "fallback_model", "budget", "priority")
        if parsed[key] is not None
    }
    if not settings:
        raise CdxError(SET_USAGE)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "sessions": parsed["sessions"],
        "provider": parsed["provider"],
        "settings": settings,
        "json": parsed["json"],
    }


def _parse_unset_args(args):
    parsed = _parse_flag_args(args, {
        "--power": {"key": "power", "type": "bool", "default": False},
        "--reasoning-effort": {"key": "reasoning_effort", "type": "bool", "default": False},
        "--permission": {"key": "permission", "type": "bool", "default": False},
        "--fast": {"key": "fast", "type": "bool", "default": False},
        "--rtk": {"key": "rtk", "type": "bool", "default": False},
        "--logics": {"key": "logics", "type": "bool", "default": False},
        "--model": {"key": "model", "type": "bool", "default": False},
        "--fallback-model": {"key": "fallback_model", "type": "bool", "default": False},
        "--budget": {"key": "budget", "type": "bool", "default": False},
        "--priority": {"key": "priority", "type": "bool", "default": False},
        "--all": {"key": "all", "type": "bool", "default": False},
        "--sessions": {"key": "sessions", "type": "str", "default": None, "transform": _parse_set_unset_sessions},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, UNSET_USAGE)},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, UNSET_USAGE, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) > 1:
        raise CdxError(UNSET_USAGE)
    if parsed["names"] and parsed["sessions"]:
        raise CdxError(UNSET_USAGE)
    if parsed["names"] and parsed["provider"]:
        raise CdxError(UNSET_USAGE)
    if parsed["sessions"] and parsed["provider"]:
        raise CdxError(UNSET_USAGE)
    if not parsed["names"] and not parsed["sessions"] and not parsed["provider"]:
        raise CdxError(UNSET_USAGE)
    _UNSET_KEYS = (
        "power", "reasoning_effort", "permission", "fast", "rtk", "logics",
        "model", "fallback_model", "budget", "priority",
    )
    keys = list(_UNSET_KEYS) if parsed["all"] else [key for key in _UNSET_KEYS if parsed[key]]
    if not keys:
        raise CdxError(UNSET_USAGE)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "sessions": parsed["sessions"],
        "provider": parsed["provider"],
        "keys": keys,
        "json": parsed["json"],
    }


def _parse_config_args(args):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, CONFIG_USAGE, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) != 1:
        raise CdxError(CONFIG_USAGE)
    return {"name": parsed["names"][0], "json": parsed["json"]}


def _parse_configs_args(args):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, CONFIGS_USAGE)
    return {"json": parsed["json"]}


def _parse_select_args(args):
    parsed = _parse_flag_args(args, {
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, SELECT_USAGE)},
        "--min-reasoning-effort": {"key": "min_reasoning_effort", "type": "str", "default": None},
        "--min-power": {"key": "min_power", "type": "str", "default": None},
        "--require-ready": {"key": "require_ready", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, SELECT_USAGE)
    if not parsed["provider"] or not parsed["json"]:
        raise CdxError(SELECT_USAGE)
    effort = _normalize_reasoning_effort(
        reasoning_effort=parsed["min_reasoning_effort"],
        power=parsed["min_power"],
        usage=SELECT_USAGE,
    ).get("reasoning_effort")
    return {
        "provider": parsed["provider"],
        "min_reasoning_effort": effort,
        "require_ready": parsed["require_ready"],
        "refresh": parsed["refresh"],
        "json": parsed["json"],
    }


def _parse_next_args(args):
    parsed = _parse_flag_args(args, {
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, NEXT_USAGE)
    return {"json": parsed["json"], "refresh": parsed["refresh"]}


def _parse_timeout_seconds(value, usage=RUN_USAGE):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise CdxError(usage) from error
    if parsed <= 0:
        raise CdxError(usage)
    return parsed


def _parse_run_timeout_seconds(value):
    try:
        return _parse_timeout_seconds(value, RUN_USAGE)
    except CdxError as error:
        raise CdxArgumentError(
            f"cdx run: --timeout-seconds must be a positive number; got {value!r}.",
            code=ARG_CODE_OUT_OF_RANGE,
            arguments=["--timeout-seconds"],
        ) from error


def _parse_run_provider(value):
    try:
        return _parse_provider_filter(value, RUN_USAGE)
    except CdxError as error:
        allowed = "|".join(PROVIDERS)
        raise CdxArgumentError(
            f"cdx run: invalid --provider {value!r}; allowed values: {allowed}.",
            code=ARG_CODE_INVALID_VALUE,
            arguments=["--provider"],
            allowed=PROVIDERS,
        ) from error


def _normalize_run_permission(value):
    if value is None:
        return None
    text = normalize_permission(value)
    if text is None:
        allowed = "|".join(RUN_PERMISSION_VALUES)
        raise CdxArgumentError(
            f"cdx run: invalid --permission {value!r}; allowed values: {allowed}.",
            code=ARG_CODE_INVALID_VALUE,
            arguments=["--permission"],
            allowed=RUN_PERMISSION_VALUES,
        )
    return text


def cdx_schema():
    """The machine-readable contract for programmatic callers.

    Every value here is the same object the parser validates against, not a
    parallel copy — `cdx schema --json` cannot advertise a value `cdx run`
    rejects, which is exactly how the ollama `--experimental-yolo` mapping
    survived unexercised (GitHub issue #8).
    """
    # No `schema_version` here: the JSON envelope already carries it, and two
    # keys of that name in one payload would be one too many.
    return {
        "enums": {
            "permission": {
                "accepted": list(RUN_PERMISSION_VALUES),
                "canonical": list(RUN_PERMISSION_CANONICAL_VALUES),
                "aliases": dict(RUN_PERMISSION_ALIASES),
            },
            "reasoning_effort": {"accepted": list(RUN_EFFORT_VALUES)},
            "power": {"accepted": list(RUN_EFFORT_VALUES)},
            "kind": {"accepted": list(RUN_KIND_VALUES)},
            "provider": {"accepted": list(PROVIDERS)},
        },
        "mutually_exclusive": [
            {
                "command": "run",
                "arguments": ["session", "--provider"],
                "reason": "A session already fixes its provider; pass one or the other.",
            },
            {
                "command": "run",
                "arguments": ["--prompt-file", "--prompt"],
                "reason": "Exactly one prompt source.",
            },
            {
                "command": "run",
                "arguments": ["--detach", "--failover"],
                "reason": "Failover has to watch the run to react to a rate limit; --detach stops watching.",
            },
        ],
        # Not mutually exclusive: both may be given, and cdx accepts them when
        # they agree. A caller generating validation from `mutually_exclusive`
        # would otherwise reject a command line cdx would have run.
        "must_match": [
            {
                "command": "run",
                "arguments": ["--reasoning-effort", "--power"],
                "reason": "Aliases of one setting; supplying both with different values fails.",
            },
        ],
        # Every code a run-family command can put in `error.code`, not just the
        # argument ones — a caller matching exhaustively over this list must not
        # fall through on a code it will certainly see.
        "error_codes": {
            "arguments": [
                ARG_CODE_MISSING,
                ARG_CODE_MUTUALLY_EXCLUSIVE,
                ARG_CODE_INVALID_VALUE,
                ARG_CODE_OUT_OF_RANGE,
                ARG_CODE_UNKNOWN,
                "invalid_reasoning_effort",
            ],
            "run": [
                "invalid_cwd",
                "session_disabled",
                "no_suitable_session",
                "provider_cli_not_found",
                "provider_start_failed",
                "provider_failed",
                "provider_timeout",
                "cdx_error",
            ],
            "run_lookup": [
                "run_not_found",
                "run_output_unavailable",
                "run_output_unreadable",
            ],
        },
        "warning_codes": [
            "network_disabled_by_permission",
            "session_selected_without_status",
            "limit_ignored_with_since",
        ],
    }


def _parse_schema_args(args):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, SCHEMA_USAGE)
    if not parsed["json"]:
        raise CdxError(SCHEMA_USAGE)
    return parsed


def _parse_run_flag_args(args, schema, usage, positionals_key=None, max_positionals=0):
    """`_parse_flag_args` is shared by every command and raises a bare usage
    error for an unrecognized flag or a value-less option. Only `run` promises a
    specific code for those, so translate here rather than teaching the shared
    parser about codes it does not need. Transforms that already raised a
    `CdxArgumentError` keep their own, more precise code."""
    try:
        return _parse_flag_args(args, schema, usage, positionals_key, max_positionals)
    except CdxArgumentError:
        raise
    except CdxError as error:
        raise CdxArgumentError(str(error), code=ARG_CODE_UNKNOWN) from error


def _parse_run_effort(reasoning_effort, power):
    try:
        return _normalize_reasoning_effort(
            reasoning_effort=reasoning_effort,
            power=power,
            usage=RUN_USAGE,
        )
    except CdxError as error:
        message = str(error)
        if "must match" in message:
            raise CdxArgumentError(
                message,
                code=ARG_CODE_MUTUALLY_EXCLUSIVE,
                arguments=["--reasoning-effort", "--power"],
            ) from error
        # An empty value raises the bare usage line, which names neither flag.
        # Blame the one actually supplied rather than guessing, since naming the
        # offending argument is the entire point of this error.
        if message.startswith("Unsupported power:") or (power is not None and reasoning_effort is None):
            argument = "--power"
        else:
            argument = "--reasoning-effort"
        # Keeps the pre-existing `invalid_reasoning_effort` code rather than
        # flattening it into the generic invalid-value one: it was already
        # specific, and callers may already branch on it. The new codes exist to
        # split what used to be indistinguishable, not to rename what wasn't.
        raise CdxArgumentError(
            message,
            code="invalid_reasoning_effort",
            arguments=[argument],
            allowed=RUN_EFFORT_VALUES,
        ) from error


def _parse_run_args(args):
    parsed = _parse_run_flag_args(args, {
        "--cwd": {"key": "cwd", "type": "str", "default": None},
        "--prompt-file": {"key": "prompt_file", "type": "str", "default": None},
        "--prompt": {"key": "prompt", "type": "str", "default": None},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": _parse_run_provider},
        "--model": {"key": "model", "type": "str", "default": None},
        "--kind": {"key": "kind", "type": "str", "default": "assistant"},
        "--reasoning-effort": {"key": "reasoning_effort", "type": "str", "default": None},
        "--power": {"key": "power", "type": "str", "default": None},
        "--permission": {"key": "permission", "type": "str", "default": None, "transform": _normalize_run_permission},
        "--timeout-seconds": {"key": "timeout_seconds", "type": "str", "default": None, "transform": _parse_run_timeout_seconds},
        "--detach": {"key": "detach", "type": "bool", "default": False},
        "--failover": {"key": "failover", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, RUN_USAGE, positionals_key="names", max_positionals=1)
    if not parsed["json"]:
        raise CdxArgumentError(RUN_JSON_REQUIRED, code=ARG_CODE_MISSING, arguments=["--json"])
    name = parsed["names"][0] if parsed["names"] else None
    if name and parsed["provider"]:
        raise CdxArgumentError(
            RUN_SESSION_PROVIDER_CONFLICT,
            code=ARG_CODE_MUTUALLY_EXCLUSIVE,
            arguments=["session", "--provider"],
        )
    if not name and not parsed["provider"]:
        raise CdxArgumentError(RUN_TARGET_REQUIRED, code=ARG_CODE_MISSING, arguments=["session", "--provider"])
    if not parsed["cwd"]:
        raise CdxArgumentError(RUN_CWD_REQUIRED, code=ARG_CODE_MISSING, arguments=["--cwd"])
    if parsed["prompt_file"] and parsed["prompt"]:
        raise CdxArgumentError(
            RUN_PROMPT_SOURCE_REQUIRED,
            code=ARG_CODE_MUTUALLY_EXCLUSIVE,
            arguments=["--prompt-file", "--prompt"],
        )
    if parsed["detach"] and parsed["failover"]:
        raise CdxArgumentError(
            RUN_DETACH_FAILOVER_CONFLICT,
            code=ARG_CODE_MUTUALLY_EXCLUSIVE,
            arguments=["--detach", "--failover"],
        )
    if not parsed["prompt_file"] and not parsed["prompt"]:
        raise CdxArgumentError(
            RUN_PROMPT_SOURCE_REQUIRED,
            code=ARG_CODE_MISSING,
            arguments=["--prompt-file", "--prompt"],
        )
    if parsed["kind"] not in RUN_KIND_VALUES:
        allowed = "|".join(RUN_KIND_VALUES)
        raise CdxArgumentError(
            f"cdx run: invalid --kind {parsed['kind']!r}; allowed values: {allowed}.",
            code=ARG_CODE_INVALID_VALUE,
            arguments=["--kind"],
            allowed=RUN_KIND_VALUES,
        )
    effort = _parse_run_effort(parsed["reasoning_effort"], parsed["power"])
    return {
        "name": name,
        "provider": parsed["provider"],
        "cwd": parsed["cwd"],
        "prompt_file": parsed["prompt_file"],
        "prompt": parsed["prompt"],
        "kind": parsed["kind"],
        "model": parsed["model"],
        "permission": parsed["permission"],
        "timeout_seconds": parsed["timeout_seconds"],
        "detach": parsed["detach"],
        "failover": parsed["failover"],
        "refresh": parsed["refresh"],
        "reasoning_effort": effort.get("reasoning_effort"),
        "power": effort.get("power"),
    }


def _parse_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise CdxError(HISTORY_USAGE) from error
    if parsed < 1:
        raise CdxError(HISTORY_USAGE)
    return parsed


def _local_timezone():
    return datetime.now().astimezone().tzinfo


def _parse_datetime_value(value, usage, end_of_day=False):
    text = str(value or "").strip()
    if not text:
        raise CdxError(usage)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    is_date_only = len(text) == 10 and text[4] == "-" and text[7] == "-"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise CdxError(usage) from error
    if is_date_only and end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_timezone())
    return parsed.astimezone()


def _parse_since_value(value, now, usage):
    text = str(value or "").strip().lower()
    if not text:
        raise CdxError(usage)
    if text == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if text == "yesterday":
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today - timedelta(days=1)
    unit = text[-1:]
    amount_text = text[:-1]
    if unit in ("m", "h", "d", "w") and amount_text.isdigit():
        amount = int(amount_text)
        if amount < 1:
            raise CdxError(usage)
        multipliers = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }
        return now - multipliers[unit]
    return _parse_datetime_value(value, usage, end_of_day=False)


def _format_period_datetime(value):
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def _parse_history_period(parsed, now, usage=HISTORY_USAGE):
    since = parsed.get("since")
    from_value = parsed.get("from")
    to_value = parsed.get("to")
    if since and from_value:
        raise CdxError(f"{usage} cannot combine --since and --from.")
    start = _parse_since_value(since, now, usage) if since else None
    if from_value:
        start = _parse_datetime_value(from_value, usage, end_of_day=False)
    end = _parse_datetime_value(to_value, usage, end_of_day=True) if to_value else None
    if start and end and start.timestamp() > end.timestamp():
        raise CdxError(f"{usage} period start must be before period end.")
    return {
        "from": _format_period_datetime(start),
        "to": _format_period_datetime(end),
        "from_ts": start.timestamp() if start else None,
        "to_ts": end.timestamp() if end else None,
    }


def _has_history_period(period):
    return period.get("from_ts") is not None or period.get("to_ts") is not None


def _parse_entry_timestamp(entry):
    value = entry.get("started_at")
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_timezone())
    return parsed.timestamp()


def _filter_history_period(entries, period):
    if not _has_history_period(period):
        return entries
    filtered = []
    start = period.get("from_ts")
    end = period.get("to_ts")
    for entry in entries:
        timestamp = _parse_entry_timestamp(entry)
        if timestamp is None:
            continue
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp > end:
            continue
        filtered.append(entry)
    return filtered


def _public_history_period(period):
    return {
        "from": period.get("from"),
        "to": period.get("to"),
    }


def _parse_history_args(args, now=None):
    now = now or datetime.now().astimezone()
    parsed = _parse_flag_args(args, {
        "--limit": {"key": "limit", "type": "str", "default": 20, "transform": _parse_positive_int},
        "--summary": {"key": "summary", "type": "bool", "default": False},
        "--since": {"key": "since", "type": "str", "default": None},
        "--from": {"key": "from", "type": "str", "default": None},
        "--to": {"key": "to", "type": "str", "default": None},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, HISTORY_USAGE, positionals_key="names", max_positionals=1)
    period = _parse_history_period(parsed, now, HISTORY_USAGE)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "limit": parsed["limit"],
        "summary": parsed["summary"],
        "period": period,
        "json": parsed["json"],
    }


def _parse_stats_args(args, now=None):
    now = now or datetime.now().astimezone()
    parsed = _parse_flag_args(args, {
        "--since": {"key": "since", "type": "str", "default": None},
        "--from": {"key": "from", "type": "str", "default": None},
        "--to": {"key": "to", "type": "str", "default": None},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, STATS_USAGE, positionals_key="names", max_positionals=1)
    period = _parse_history_period(parsed, now, STATS_USAGE)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "period": period,
        "json": parsed["json"],
    }


def _read_option_value(args, index, usage, schema=None):
    if index + 1 >= len(args):
        raise CdxError(usage)
    value = args[index + 1]
    # A known flag is never a value: '--model --json' is a missing value,
    # not model='--json'. Literal flag-like values remain expressible as
    # '--model=--json'.
    if schema and value in schema:
        raise CdxError(usage)
    return value, index + 2


def _parse_session_names(value):
    if value is None:
        return None
    names = [item.strip() for item in value.split(",") if item.strip()]
    if not names:
        raise CdxError("At least one session name is required in --sessions.")
    return names


def _parse_set_unset_sessions(value):
    text = str(value or "").strip()
    if not text:
        raise CdxError("At least one session name is required in --sessions.")
    if text.lower() == "all":
        return "all"
    return _parse_session_names(text)


def _parse_provider_filter(value, usage):
    provider = str(value or "").strip()
    if provider not in PROVIDERS:
        raise CdxError(usage)
    return provider


def _parse_launch_setting_target(value, usage):
    text = str(value or "").strip()
    if not text:
        raise CdxError(usage)
    if text == "all":
        return {"name": None, "sessions": "all", "provider": None}
    if text.startswith("provider:"):
        return {"name": None, "sessions": None, "provider": _parse_provider_filter(text.split(":", 1)[1], usage)}
    if "," in text:
        return {"name": None, "sessions": _parse_session_names(text), "provider": None}
    return {"name": text, "sessions": None, "provider": None}


def _parse_launch_setting_alias_args(kind, args):
    json_flag, cleaned = _parse_json_flag(args)
    if len(cleaned) != 2:
        raise CdxError(SETTING_ALIAS_USAGE)
    target = _parse_launch_setting_target(cleaned[0], SETTING_ALIAS_USAGE)
    value = cleaned[1]
    field = "permission" if kind == "perm" else kind
    if value == "default":
        return {**target, "keys": [field], "json": json_flag, "alias": kind}
    if field == "fast":
        value = _parse_fast_value(value)
    return {**target, "settings": {field: value}, "json": json_flag, "alias": kind}


def _parse_update_args(args):
    parsed = _parse_flag_args(args, {
        "--check": {"key": "check", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
        "--yes": {"key": "yes", "type": "bool", "default": False},
        "--version": {"key": "version", "type": "str", "default": None},
    }, UPDATE_USAGE, positionals_key="values", max_positionals=1)
    if parsed["values"] not in ([], ["all"]):
        raise CdxError(UPDATE_USAGE)
    parsed["all"] = bool(parsed["values"])
    if parsed["all"] and (parsed["check"] or parsed["version"]):
        raise CdxError("Usage: cdx update all [--yes] [--json]")
    if parsed["check"] and parsed["version"]:
        raise CdxError("Usage: cdx update --check cannot be combined with --version.")
    if parsed["version"] is not None and not parsed["version"].strip():
        raise CdxError(UPDATE_USAGE)
    return parsed


def _parse_export_args(args):
    parsed = _parse_flag_args(args, {
        "--include-auth": {"key": "include_auth", "type": "bool", "default": False},
        "--force": {"key": "force", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
        "--sessions": {
            "key": "session_names",
            "type": "str",
            "default": None,
            "transform": _parse_session_names,
        },
        "--passphrase-env": {"key": "passphrase_env", "type": "str", "default": None},
        "--passphrase-stdin": {"key": "passphrase_stdin", "type": "bool", "default": False},
    }, EXPORT_USAGE, positionals_key="positionals", max_positionals=1)
    parsed["file_path"] = parsed.pop("positionals")[0] if parsed["positionals"] else None
    if not parsed["file_path"]:
        raise CdxError(EXPORT_USAGE)
    if parsed["passphrase_env"] and parsed["passphrase_stdin"]:
        raise CdxError("--passphrase-env and --passphrase-stdin are mutually exclusive.")
    if (parsed["passphrase_env"] or parsed["passphrase_stdin"]) and not parsed["include_auth"]:
        raise CdxError("--passphrase-env/--passphrase-stdin requires --include-auth for export.")
    return parsed


def _parse_import_args(args):
    parsed = _parse_flag_args(args, {
        "--force": {"key": "force", "type": "bool", "default": False},
        "--merge": {"key": "merge", "type": "bool", "default": False},
        "--allow-authless-force": {"key": "allow_authless_force", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
        "--sessions": {
            "key": "session_names",
            "type": "str",
            "default": None,
            "transform": _parse_session_names,
        },
        "--passphrase-env": {"key": "passphrase_env", "type": "str", "default": None},
        "--passphrase-stdin": {"key": "passphrase_stdin", "type": "bool", "default": False},
    }, IMPORT_USAGE, positionals_key="positionals", max_positionals=1)
    parsed["file_path"] = parsed.pop("positionals")[0] if parsed["positionals"] else None
    if not parsed["file_path"]:
        raise CdxError(IMPORT_USAGE)
    if parsed["force"] and parsed["merge"]:
        raise CdxError("--force and --merge are mutually exclusive.")
    if parsed["passphrase_env"] and parsed["passphrase_stdin"]:
        raise CdxError("--passphrase-env and --passphrase-stdin are mutually exclusive.")
    return parsed


def _parse_runs_args(rest, now=None):
    now = now or datetime.now().astimezone()
    parsed = _parse_flag_args(rest, {
        "--limit": {"key": "limit", "type": "str", "default": 20, "transform": _parse_positive_int},
        "--since": {"key": "since", "type": "str", "default": None},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, RUNS_USAGE, max_positionals=0)
    since = None
    if parsed["since"] is not None:
        # Same cursor forms as `cdx history --since`, parsed by the same code:
        # a caller that learned one syntax does not learn a second one.
        since = _parse_since_value(parsed["since"], now, RUNS_USAGE)
    return {
        "limit": parsed["limit"],
        "since": since,
        # A cursor selects by completion time, not by row count. Keeping the
        # caller's own --limit would silently reintroduce the miss it removes:
        # a watchdog behind by more than `limit` completions would never see
        # the older ones at all.
        "limit_given": any(arg == "--limit" or arg.startswith("--limit=") for arg in rest),
        "json": parsed["json"],
    }


def _parse_run_id_json_args(rest, usage):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, usage, positionals_key="ids", max_positionals=1)
    if not parsed["json"] or len(parsed["ids"]) != 1:
        raise CdxError(usage)
    return {"run_id": parsed["ids"][0], "json": True}


def _parse_run_tail_args(rest):
    parsed = _parse_flag_args(rest, {
        "--lines": {"key": "lines", "type": "str", "default": RUN_TAIL_DEFAULT_LINES,
                    "transform": _parse_run_tail_lines},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, RUN_TAIL_USAGE, positionals_key="ids", max_positionals=1)
    if not parsed["json"] or len(parsed["ids"]) != 1:
        raise CdxError(RUN_TAIL_USAGE)
    return {"run_id": parsed["ids"][0], "lines": parsed["lines"], "json": True}


def _parse_run_tail_lines(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise CdxArgumentError(
            f"cdx run-tail: --lines must be an integer; got {value!r}.",
            code=ARG_CODE_INVALID_VALUE,
            arguments=["--lines"],
        ) from error
    if not 1 <= parsed <= RUN_TAIL_MAX_LINES:
        raise CdxArgumentError(
            f"cdx run-tail: --lines must be between 1 and {RUN_TAIL_MAX_LINES}; got {parsed}.",
            code=ARG_CODE_OUT_OF_RANGE,
            arguments=["--lines"],
        )
    return parsed
