#!/usr/bin/env python3
"""Argument parsers and usage strings for cdx commands.

Split out of cli_commands.py: pure input-parsing layer (no command execution),
imported back there and used by the handlers.
"""

from datetime import datetime, timedelta

from .config import PROVIDER_CODEX, PROVIDERS
from .errors import CdxError
from .provider_runtime import _normalize_reasoning_effort

STATUS_USAGE = "Usage: cdx status [--json] [--refresh|--cached] [--timeout SECONDS] | cdx status --small|-s [--refresh|--cached] [--timeout SECONDS] | cdx status <name> [--json] [--refresh|--cached] [--timeout SECONDS]"
DOCTOR_USAGE = "Usage: cdx doctor [--json]"
DISK_USAGE = "Usage: cdx disk [profiles] [--candidates] [--json]"
REPAIR_USAGE = "Usage: cdx repair [--dry-run] [--force] [--json]"
UPDATE_USAGE = "Usage: cdx update [--check] [--yes] [--json] [--version TAG]"
EXPORT_USAGE = "Usage: cdx export <file> [--include-auth] [--force] [--json] [--sessions name1,name2] [--passphrase-env VAR|--passphrase-stdin]"
IMPORT_USAGE = "Usage: cdx import <file> [--force|--merge] [--allow-authless-force] [--json] [--sessions name1,name2] [--passphrase-env VAR|--passphrase-stdin]"
CONTEXT_USAGE = "Usage: cdx context show|path|init|edit|clear|set [text...] [--json]"
HANDOFF_USAGE = "Usage: cdx handoff <name> [--json] | cdx handoff <source> <target> [--json]"
SET_USAGE = "Usage: cdx set <name>|--sessions all|a,b|--provider PROVIDER [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full] [--fast on|off] [--rtk on|off] [--logics on|off] [--model MODEL] [--priority 0..100] [--json]"
UNSET_USAGE = "Usage: cdx unset <name>|--sessions all|a,b|--provider PROVIDER (--power|--permission|--fast|--rtk|--logics|--model|--priority|--all) [--json]"
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
RUN_USAGE = "Usage: cdx run [session] --cwd PATH (--prompt-file PATH|--prompt TEXT) [--provider PROVIDER] [--model MODEL] [--kind assistant|code-review] [--reasoning-effort minimal|low|medium|high|xhigh] [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full|workspace-write|read-only|danger-full-access] [--timeout-seconds N] --json"
RUNS_USAGE = "Usage: cdx runs [--limit N] --json"
RUN_STATUS_USAGE = "Usage: cdx run-status <run_id> --json"
RUN_REPORT_USAGE = "Usage: cdx run-report <run_id> --json"


def _parse_json_flag(args):
    json_flag = "--json" in args
    cleaned = [arg for arg in args if arg != "--json"]
    return json_flag, cleaned


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


def _parse_set_args(args):
    parsed = _parse_flag_args(args, {
        "--power": {"key": "power", "type": "str", "default": None},
        "--permission": {"key": "permission", "type": "str", "default": None},
        "--fast": {"key": "fast", "type": "str", "default": None, "transform": _parse_fast_value},
        "--rtk": {"key": "rtk", "type": "str", "default": None, "transform": _parse_fast_value},
        "--logics": {"key": "logics", "type": "str", "default": None, "transform": _parse_fast_value},
        "--model": {"key": "model", "type": "str", "default": None},
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
        for key in ("power", "permission", "fast", "rtk", "logics", "model", "priority")
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
        "--permission": {"key": "permission", "type": "bool", "default": False},
        "--fast": {"key": "fast", "type": "bool", "default": False},
        "--rtk": {"key": "rtk", "type": "bool", "default": False},
        "--logics": {"key": "logics", "type": "bool", "default": False},
        "--model": {"key": "model", "type": "bool", "default": False},
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
    keys = ["power", "permission", "fast", "rtk", "logics", "model", "priority"] if parsed["all"] else [
        key for key in ("power", "permission", "fast", "rtk", "logics", "model", "priority") if parsed[key]
    ]
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


def _normalize_run_permission(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    aliases = {
        "workspace-write": "default",
        "read-only": "review",
        "danger-full-access": "full",
    }
    text = aliases.get(text, text)
    if text not in ("review", "default", "auto", "full"):
        raise CdxError(RUN_USAGE)
    return text


def _parse_run_args(args):
    parsed = _parse_flag_args(args, {
        "--cwd": {"key": "cwd", "type": "str", "default": None},
        "--prompt-file": {"key": "prompt_file", "type": "str", "default": None},
        "--prompt": {"key": "prompt", "type": "str", "default": None},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, RUN_USAGE)},
        "--model": {"key": "model", "type": "str", "default": None},
        "--kind": {"key": "kind", "type": "str", "default": "assistant"},
        "--reasoning-effort": {"key": "reasoning_effort", "type": "str", "default": None},
        "--power": {"key": "power", "type": "str", "default": None},
        "--permission": {"key": "permission", "type": "str", "default": None, "transform": _normalize_run_permission},
        "--timeout-seconds": {"key": "timeout_seconds", "type": "str", "default": None, "transform": _parse_timeout_seconds},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, RUN_USAGE, positionals_key="names", max_positionals=1)
    if not parsed["json"]:
        raise CdxError(RUN_USAGE)
    name = parsed["names"][0] if parsed["names"] else None
    if name and parsed["provider"]:
        raise CdxError(RUN_USAGE)
    if not name and not parsed["provider"]:
        raise CdxError(RUN_USAGE)
    if not parsed["cwd"]:
        raise CdxError(RUN_USAGE)
    if bool(parsed["prompt_file"]) == bool(parsed["prompt"]):
        raise CdxError(RUN_USAGE)
    if parsed["kind"] not in ("assistant", "code-review"):
        raise CdxError(RUN_USAGE)
    effort = _normalize_reasoning_effort(
        reasoning_effort=parsed["reasoning_effort"],
        power=parsed["power"],
        usage=RUN_USAGE,
    )
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


def _parse_history_period(parsed, now):
    since = parsed.get("since")
    from_value = parsed.get("from")
    to_value = parsed.get("to")
    if since and from_value:
        raise CdxError("Usage: cdx history cannot combine --since and --from.")
    start = _parse_since_value(since, now, HISTORY_USAGE) if since else None
    if from_value:
        start = _parse_datetime_value(from_value, HISTORY_USAGE, end_of_day=False)
    end = _parse_datetime_value(to_value, HISTORY_USAGE, end_of_day=True) if to_value else None
    if start and end and start.timestamp() > end.timestamp():
        raise CdxError("Usage: cdx history period start must be before period end.")
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
    period = _parse_history_period(parsed, now)
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
    period = _parse_history_period(parsed, now)
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
    }, UPDATE_USAGE)
    if parsed["check"] and parsed["version"]:
        raise CdxError("Usage: cdx update --check cannot be combined with --version.")
    if parsed["version"] is not None and not parsed["version"].strip():
        raise CdxError("Usage: cdx update [--check] [--yes] [--json] [--version TAG]")
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


def _parse_runs_args(rest):
    return _parse_flag_args(rest, {
        "--limit": {"key": "limit", "type": "str", "default": 20, "transform": _parse_positive_int},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, RUNS_USAGE, max_positionals=0)


def _parse_run_id_json_args(rest, usage):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, usage, positionals_key="ids", max_positionals=1)
    if not parsed["json"] or len(parsed["ids"]) != 1:
        raise CdxError(usage)
    return {"run_id": parsed["ids"][0], "json": True}
