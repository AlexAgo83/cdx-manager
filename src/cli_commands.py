import getpass
import json
import os
import re
import shlex
import sys
import time
import uuid
from datetime import datetime

from .backup_bundle import read_bundle_meta
from .claude_refresh import _refresh_claude_sessions
from .cli_args import (
    CAN_RESUME_USAGE,
    CONTEXT_USAGE,
    HANDOFF_USAGE,
    LAST_USAGE,
    MEMORY_USAGE,
    RESUME_USAGE,
    STATUS_USAGE,
    _filter_history_period,
    _has_history_period,
    _parse_add_args,
    _parse_config_args,
    _parse_configs_args,
    _parse_copy_args,
    _parse_export_args,
    _parse_flag_args,
    _parse_history_args,
    _parse_import_args,
    _parse_json_flag,
    _parse_label_args,
    _parse_launch_setting_alias_args,
    _parse_next_args,
    _parse_remove_args,
    _parse_rename_args,
    _parse_set_args,
    _parse_stats_args,
    _parse_timeout_seconds,
    _parse_toggle_args,
    _parse_unset_args,
    _public_history_period,
)
from .cli_helpers import (
    API_SCHEMA_VERSION,
    _build_handoff_context,
    _format_bytes,
    _format_export_report,
    _handoff_launch_prompt,
    _json_failure,
    _json_success,
    _latest_handoff_transcript_path,
    _local_now_iso,
    _make_export_progress,
    _make_notify_progress,
    _make_status_progress,
    _read_handoff_transcript,
    _resolve_confirmation,
    _update_notice_warnings,
    _write_json,
    _write_update_notice,
)
from .cli_render import _dim, _info, _pad_table, _style, _success, _warn
from .cli_view import handle_view as handle_view  # re-export for cli.py / tests
from .codex_usage import consume_codex_rate_limit_reset_credit
from .commands.maintenance import (  # re-export for cli.py / tests
    _candidate as _candidate,
)
from .commands.maintenance import (
    _clean_profile_old_logs as _clean_profile_old_logs,
)
from .commands.maintenance import (
    _clean_profile_tmp as _clean_profile_tmp,
)
from .commands.maintenance import (
    _collect_old_logs as _collect_old_logs,
)
from .commands.maintenance import (
    _collect_profile_cleanup_candidates as _collect_profile_cleanup_candidates,
)
from .commands.maintenance import (
    _confirm_log_cleanup as _confirm_log_cleanup,
)
from .commands.maintenance import (
    _confirm_profile_cleanup as _confirm_profile_cleanup,
)
from .commands.maintenance import (
    _directory_child_sizes as _directory_child_sizes,
)
from .commands.maintenance import (
    _directory_size_bytes as _directory_size_bytes,
)
from .commands.maintenance import (
    _format_cleanup_candidates as _format_cleanup_candidates,
)
from .commands.maintenance import (
    _format_disk_report as _format_disk_report,
)
from .commands.maintenance import (
    _format_update_all as _format_update_all,
)
from .commands.maintenance import (
    _format_update_all_result as _format_update_all_result,
)
from .commands.maintenance import (
    _handle_clean_profiles as _handle_clean_profiles,
)
from .commands.maintenance import (
    _iter_profile_dirs as _iter_profile_dirs,
)
from .commands.maintenance import (
    _parse_days as _parse_days,
)
from .commands.maintenance import (
    _remove_path as _remove_path,
)
from .commands.maintenance import (
    handle_clean as handle_clean,
)
from .commands.maintenance import (
    handle_disk as handle_disk,
)
from .commands.maintenance import (
    handle_doctor as handle_doctor,
)
from .commands.maintenance import (
    handle_repair as handle_repair,
)
from .commands.maintenance import (
    handle_update as handle_update,
)
from .commands.runs import (  # re-export for cli.py / tests
    DETACHED_PROMPT_SUFFIX as DETACHED_PROMPT_SUFFIX,
)
from .commands.runs import (
    DETACHED_RUN_ID_ENV as DETACHED_RUN_ID_ENV,
)
from .commands.runs import (
    RUN_TAIL_READ_BYTES as RUN_TAIL_READ_BYTES,
)
from .commands.runs import (
    _cdx_self_command as _cdx_self_command,
)
from .commands.runs import (
    _consume_detached_prompt_file as _consume_detached_prompt_file,
)
from .commands.runs import (
    _detached_child_argv as _detached_child_argv,
)
from .commands.runs import (
    _detached_spawn_options as _detached_spawn_options,
)
from .commands.runs import (
    _run_registry as _run_registry,
)
from .commands.runs import (
    _select_headless_session as _select_headless_session,
)
from .commands.runs import (
    _selection_reason as _selection_reason,
)
from .commands.runs import (
    _spawn_detached_run as _spawn_detached_run,
)
from .commands.runs import (
    _tail_file_lines as _tail_file_lines,
)
from .commands.runs import (
    handle_run as handle_run,
)
from .commands.runs import (
    handle_run_report as handle_run_report,
)
from .commands.runs import (
    handle_run_status as handle_run_status,
)
from .commands.runs import (
    handle_run_tail as handle_run_tail,
)
from .commands.runs import (
    handle_runs as handle_runs,
)
from .commands.runs import (
    handle_schema as handle_schema,
)
from .commands.runs import (
    handle_select as handle_select,
)
from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA
from .context_store import (
    append_context,
    append_context_path,
    clear_context,
    clear_context_path,
    edit_context,
    edit_context_path,
    get_context_path,
    get_global_context_path,
    get_named_project_context_path,
    init_context,
    init_context_path,
    install_context_for_session,
    list_named_project_contexts,
    read_context,
    read_context_path,
    write_context,
    write_context_path,
)
from .errors import CdxError
from .fs_utils import atomic_write
from .notify import (
    format_notify_event,
    format_scheduled_notification,
    parse_notify_args,
    resolve_notify_event,
    schedule_notification_event,
    send_desktop_notification,
    wait_for_notification_event,
)
from .provider_runtime import (
    AUTH_PROBE_AUTHENTICATED,
    AUTH_PROBE_DEGRADED,
    _ensure_session_authentication,
    _probe_provider_auth_status,
    _run_interactive_provider_command,
    get_resume_capability,
)
from .status_view import (
    _format_status_detail,
    _format_status_rows,
    format_priority_instruction,
    recommend_priority_rows,
)


def _resolve_bundle_passphrase(ctx, env_var, prompt, confirm=False, use_stdin=False):
    env = ctx.get("env", {})
    if env_var:
        passphrase = env.get(env_var)
        if not passphrase:
            raise CdxError(f"Environment variable {env_var} is empty or unset.")
        return passphrase
    if use_stdin:
        reader = ctx["options"].get("read_stdin")
        raw = reader() if callable(reader) else sys.stdin.readline()
        passphrase = (raw or "").rstrip("\r\n")
        if not passphrase:
            raise CdxError("Bundle passphrase from stdin is empty.")
        return passphrase
    if not ctx["stdin_is_tty"]:
        raise CdxError("Encrypted bundle export/import requires an interactive terminal, --passphrase-env, or --passphrase-stdin.")
    getpass_fn = ctx["options"].get("getpass") or getpass.getpass
    passphrase = getpass_fn(prompt)
    if not passphrase:
        raise CdxError("Bundle passphrase cannot be empty.")
    if confirm:
        confirmation = getpass_fn("Confirm bundle passphrase: ")
        if passphrase != confirmation:
            raise CdxError("Bundle passphrase confirmation does not match.")
    return passphrase


def _confirm_removal(name):
    answer = input(f"Remove session {name}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def _confirm_reset(name):
    answer = input(f"Consume one banked Codex reset for {name}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def _extract_claude_oauth_token(text):
    if not text:
        return None
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", str(text))
    patterns = [
        r"CLAUDE_CODE_OAUTH_TOKEN=([^\s\"']+)",
        r"(sk-ant-oat[0-9A-Za-z._-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            token = match.group(1).strip()
            if token.startswith("<") or any(ord(ch) < 32 or ord(ch) == 127 for ch in token):
                continue
            return token
    return None


def _write_claude_oauth_token(auth_home, token):
    cred_dir = os.path.join(auth_home, "credentials")
    os.makedirs(cred_dir, mode=0o700, exist_ok=True)
    try:
        os.chmod(cred_dir, 0o700)
    except OSError:
        pass
    cred_path = os.path.join(cred_dir, "default.json")
    payload = {
        "version": "1.0",
        "type": "oauth_token",
        "access_token": token,
    }
    # atomic_write keeps the token 0o600 from creation — no umask window.
    atomic_write(cred_path, json.dumps(payload, indent=2) + "\n", mode=0o600)
    return cred_path


def _bootstrap_claude_setup_token(session, ctx):
    ctx["out"](
        "Claude login did not create isolated credentials; falling back to claude setup-token.\n"
    )
    run_info = _run_interactive_provider_command(
        session,
        "setup-token",
        spawn=ctx.get("spawn"),
        env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter"),
    )
    transcript_path = run_info.get("transcript_path")
    if not transcript_path or not os.path.isfile(transcript_path):
        raise CdxError(
            "Claude setup-token completed, but cdx could not capture the token. "
            "Run claude setup-token and save the token under credentials/default.json."
        )
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as handle:
            transcript = handle.read()
    finally:
        # The transcript holds the ~1-year OAuth token in cleartext; it must
        # not outlive the extraction, whether it succeeds or not.
        try:
            os.remove(transcript_path)
        except OSError:
            pass
    token = _extract_claude_oauth_token(transcript)
    if not token:
        raise CdxError(
            "Claude setup-token completed, but cdx could not find CLAUDE_CODE_OAUTH_TOKEN in the output. "
            "Run claude setup-token manually and save the token under credentials/default.json."
        )
    auth_home = session.get("authHome") or ""
    cred_path = _write_claude_oauth_token(auth_home, token)
    # ponytail: drop short-lived claude login creds so the ~1yr token wins at launch (provider_runtime _read_claude_launch_oauth_token)
    try:
        os.remove(os.path.join(auth_home, ".claude", ".credentials.json"))
    except OSError:
        pass
    return cred_path


def handle_add(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_add_args(args)
    if parsed["provider"] == PROVIDER_OLLAMA and not parsed.get("model"):
        raise CdxError("Usage: cdx add ollama <name> --model MODEL [--json]")
    if parsed.get("model") and parsed["provider"] != PROVIDER_OLLAMA:
        raise CdxError("--model is only supported when adding an ollama session.")
    session = ctx["service"]["create_session"](parsed["name"], parsed["provider"])
    if parsed.get("model"):
        session = ctx["service"]["set_launch_settings"](parsed["name"], {"model": parsed["model"]})
    message = f"Created session {parsed['name']} ({parsed['provider']})"
    if session["provider"] == PROVIDER_CLAUDE and ctx["stdin_is_tty"]:
        # ponytail: mint a ~1yr setup-token instead of the ~daily claude login token
        _bootstrap_claude_setup_token(session, ctx)
    else:
        _ensure_session_authentication(
            session,
            ctx["service"],
            spawn=ctx.get("spawn"),
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
            stdin_is_tty=ctx["stdin_is_tty"],
            behavior="bootstrap",
            signal_emitter=ctx.get("signal_emitter"),
        )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](parsed["name"], lambda auth: {
        **auth,
        "status": "authenticated",
        "lastCheckedAt": now,
        "lastAuthenticatedAt": now,
        "lastLoggedOutAt": auth.get("lastLoggedOutAt"),
    })
    if json_flag:
        _write_json(ctx, _json_success(
            "add",
            message,
            session=ctx["service"]["get_session"](parsed["name"]),
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_copy(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_copy_args(args)
    result = ctx["service"]["copy_session"](parsed["source"], parsed["dest"])
    overwritten = " (overwritten)" if result["overwritten"] else ""
    message = f"Copied session {parsed['source']} to {parsed['dest']}{overwritten}"
    if json_flag:
        _write_json(ctx, _json_success(
            "copy",
            message,
            session=result["session"],
            overwritten=result["overwritten"],
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_rename(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_rename_args(args)
    session = ctx["service"]["rename_session"](parsed["source"], parsed["dest"])
    message = f"Renamed session {parsed['source']} to {parsed['dest']}"
    if json_flag:
        _write_json(ctx, _json_success("rename", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_label(rest, ctx):
    parsed = _parse_label_args(rest)
    if parsed["clear"]:
        session = ctx["service"]["clear_session_label"](parsed["name"])
        message = f"Cleared label for {parsed['name']}"
    else:
        session = ctx["service"]["set_session_label"](parsed["name"], parsed["label"])
        message = f"Set label for {parsed['name']}: {session['label']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("label", message, session=session, label=session.get("label")))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_remove(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_remove_args(args)
    if not parsed["force"]:
        confirm_fn = ctx["options"].get("confirmRemove")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, parsed["name"])
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Removal requires confirmation in an interactive terminal or --force in non-interactive mode.")
        else:
            confirmed = _confirm_removal(parsed["name"])
        if not confirmed:
            if json_flag:
                _write_json(ctx, _json_success("remove", "Cancelled.", cancelled=True, session=None))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0
    removed = ctx["service"]["remove_session"](parsed["name"])
    message = f"Removed session {parsed['name']}"
    if json_flag:
        _write_json(ctx, _json_success("remove", message, session=removed, cancelled=False))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_disable(rest, ctx):
    parsed = _parse_toggle_args(rest, "Usage: cdx disable <name> [--json]")
    session = ctx["service"]["set_session_enabled"](parsed["name"], False)
    message = f"Disabled session {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("disable", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_enable(rest, ctx):
    parsed = _parse_toggle_args(rest, "Usage: cdx enable <name> [--json]")
    session = ctx["service"]["set_session_enabled"](parsed["name"], True)
    message = f"Enabled session {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("enable", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def _format_next_pct(value):
    return "n/a" if value is None else f"{value}%"


def _next_action(row):
    instruction = format_priority_instruction(row, "first")
    return "refresh" if instruction.startswith("refresh ") else "use"


def _format_next_selection(session, row, use_color=False):
    from .cli_render import _pad_table

    action = _next_action(row)
    command = f"cdx status {session['name']} --refresh" if action == "refresh" else f"cdx {session['name']}"
    rows = [[_style(value, "1", use_color) for value in ["SESSION", "PROVIDER", "OK", "5H", "WEEK", "REASON"]]]
    rows.append([
        _style(session["name"], "36", use_color),
        _dim(session.get("provider") or "-", use_color),
        _format_next_pct(row.get("available_pct")),
        _format_next_pct(row.get("remaining_5h_pct")),
        _format_next_pct(row.get("remaining_week_pct")),
        format_priority_instruction(row, "first"),
    ])
    return "\n".join([
        _style("Next assistant:", "1", use_color),
        _pad_table(rows),
        "",
        f"{_style('Run:', '1', use_color)} {_style(command, '36', use_color)}",
    ])


def handle_next(rest, ctx):
    parsed = _parse_next_args(rest)
    rows = ctx["service"]["get_status_rows"](force_refresh=parsed["refresh"])
    priority = recommend_priority_rows(rows)
    if not priority:
        message = "No usable session status yet."
        if parsed["json"]:
            _write_json(ctx, _json_failure("next", "no_suitable_session", message, selection_policy="status_priority"))
            return 1
        ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
        return 1
    row = priority[0]
    session_name = row.get("session_name")
    session = ctx["service"]["get_session"](session_name)
    if not session:
        message = f"Selected status row has no matching session: {session_name}"
        if parsed["json"]:
            _write_json(ctx, _json_failure("next", "missing_session", message, selection_policy="status_priority", row=row))
            return 1
        raise CdxError(message)
    action = _next_action(row)
    message = f"Selected next session {session['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "next",
            message,
            session=session,
            row=row,
            recommended_action=action,
            command=f"cdx status {session['name']} --refresh" if action == "refresh" else f"cdx {session['name']}",
            reason=format_priority_instruction(row, "first"),
            selection_policy="status_priority",
        ))
        return 0
    ctx["out"](f"{_format_next_selection(session, row, ctx['use_color'])}\n")
    return 0


def _format_launch_config(session, use_color=False):
    from .cli_render import _dim, _pad_table, _style

    launch = session.get("launch") or {}
    rows = [[_style("SETTING", "1", use_color), _style("VALUE", "1", use_color)]]
    for key, label in [
        ("power", "Power"),
        ("permission", "Permission"),
        ("fast", "Fast"),
        ("rtk", "RTK"),
        ("logics", "Logics"),
        ("model", "Model"),
        ("priority", "Priority"),
    ]:
        rows.append([
            _dim(label, use_color),
            _format_launch_setting_value(launch, key, use_color=use_color),
        ])
    provider_label = f"({session['provider']})"
    return "\n".join([
        _style("Launch settings:", "1", use_color),
        f"{_style(session['name'], '36', use_color)} {_dim(provider_label, use_color)}",
        _pad_table(rows),
        "",
        _dim(_format_launch_settings_hint(session["name"]), use_color),
    ])


def _format_launch_settings_hint(name="<name>"):
    return (
        f"Set a value: cdx set {name} --power medium --permission auto "
        "--fast on --rtk on --logics on --model MODEL --priority 80"
    )


def _format_launch_setting_value(launch, key, use_color=False):
    if key in ("fast", "rtk", "logics"):
        if launch.get(key) is True:
            return _style("on", "32", use_color)
        if launch.get(key) is False:
            return _style("off", "2", use_color)
        if key == "logics":
            return _dim("auto", use_color)
        return _dim("default", use_color)
    value = launch.get(key)
    if value is None or value == "":
        return _dim("default", use_color)
    if key == "priority":
        return _style(str(value), "33", use_color)
    if key == "power":
        return _style(str(value), "96", use_color)
    if key == "permission":
        return _style(str(value), "32", use_color)
    return str(value)


def _format_launch_configs(sessions, use_color=False):
    from .cli_render import _dim, _pad_table, _style

    if not sessions:
        return "\n".join([
            _style("Launch settings:", "1", use_color),
            "No sessions.",
            "",
            _dim(_format_launch_settings_hint(), use_color),
        ])
    rows = [[_style(value, "1", use_color) for value in [
        "SESSION", "PROVIDER", "POWER", "PERMISSION", "FAST", "RTK", "LOGICS", "MODEL", "PRIORITY"
    ]]]
    for session in sessions:
        launch = session.get("launch") or {}
        rows.append([
            _style(session["name"], "36", use_color),
            _dim(session.get("provider") or "-", use_color),
            _format_launch_setting_value(launch, "power", use_color),
            _format_launch_setting_value(launch, "permission", use_color),
            _format_launch_setting_value(launch, "fast", use_color),
            _format_launch_setting_value(launch, "rtk", use_color),
            _format_launch_setting_value(launch, "logics", use_color),
            _format_launch_setting_value(launch, "model", use_color),
            _format_launch_setting_value(launch, "priority", use_color),
        ])
    return "\n".join([
        _style("Launch settings:", "1", use_color),
        _pad_table(rows),
        "",
        _dim(_format_launch_settings_hint(), use_color),
    ])


def _resolve_bulk_launch_targets(parsed, service):
    sessions = service["list_sessions"]()
    by_name = {session["name"]: session for session in sessions}
    if parsed.get("name"):
        session = by_name.get(parsed["name"])
        if not session:
            raise CdxError(f"Unknown session: {parsed['name']}")
        targets = [session]
    elif parsed.get("sessions") == "all":
        targets = sessions
    elif parsed.get("sessions"):
        targets = []
        for name in parsed["sessions"]:
            session = by_name.get(name)
            if not session:
                raise CdxError(f"Unknown session: {name}")
            targets.append(session)
    else:
        targets = sessions
    if parsed.get("provider"):
        targets = [session for session in targets if session["provider"] == parsed["provider"]]
    if not targets:
        raise CdxError("No sessions matched.")
    return targets


def _format_bulk_launch_summary(sessions):
    names = [session["name"] for session in sessions]
    if len(names) <= 8:
        return ", ".join(names)
    return ", ".join(names[:8]) + f", +{len(names) - 8} more"


def _format_duration_ms(value):
    if value is None:
        return "-"
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return str(value)
    if amount < 1000:
        return f"{amount}ms"
    seconds = amount / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {remaining:02d}s"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        return f"{hours}h {remaining_minutes:02d}m"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours:02d}h"


def _summarize_history(entries):
    by_session = {}
    for entry in entries:
        name = entry.get("session_name") or "-"
        row = by_session.setdefault(name, {
            "session_name": name,
            "provider": entry.get("provider") or "-",
            "launches": 0,
            "successes": 0,
            "failures": 0,
            "duration_ms": 0,
            "last_started_at": None,
        })
        row["launches"] += 1
        if entry.get("status") == "success":
            row["successes"] += 1
        elif entry.get("status") == "failed":
            row["failures"] += 1
        try:
            row["duration_ms"] += int(entry.get("duration_ms") or 0)
        except (TypeError, ValueError):
            pass
        started = entry.get("started_at")
        if started and (not row["last_started_at"] or started > row["last_started_at"]):
            row["last_started_at"] = started
            row["provider"] = entry.get("provider") or row["provider"]
    return sorted(
        by_session.values(),
        key=lambda item: (item["duration_ms"], item.get("last_started_at") or "", item["session_name"]),
        reverse=True,
    )


def _token_value(usage, key):
    if not isinstance(usage, dict):
        return None
    value = usage.get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _summarize_stats(entries):
    rows = {}
    for entry in entries:
        name = entry.get("session_name") or "-"
        row = rows.setdefault(name, {
            "session_name": name,
            "provider": entry.get("provider") or "-",
            "launches": 0,
            "successes": 0,
            "failures": 0,
            "duration_ms": 0,
            "usage_runs": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "last_started_at": None,
        })
        row["launches"] += 1
        if entry.get("status") == "success":
            row["successes"] += 1
        elif entry.get("status") == "failed":
            row["failures"] += 1
        try:
            row["duration_ms"] += int(entry.get("duration_ms") or 0)
        except (TypeError, ValueError):
            pass
        usage = entry.get("usage") if isinstance(entry.get("usage"), dict) else {}
        parsed_usage = {
            key: _token_value(usage, key)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")
        }
        if any(value is not None for value in parsed_usage.values()):
            row["usage_runs"] += 1
            for key, value in parsed_usage.items():
                row[key] += value or 0
        started = entry.get("started_at")
        if started and (not row["last_started_at"] or started > row["last_started_at"]):
            row["last_started_at"] = started
            row["provider"] = entry.get("provider") or row["provider"]
    return sorted(
        rows.values(),
        key=lambda item: (item["total_tokens"], item["duration_ms"], item.get("last_started_at") or "", item["session_name"]),
        reverse=True,
    )


def _stats_totals(rows):
    return {
        "sessions": len(rows),
        "launches": sum(row["launches"] for row in rows),
        "successes": sum(row["successes"] for row in rows),
        "failures": sum(row["failures"] for row in rows),
        "duration_ms": sum(row["duration_ms"] for row in rows),
        "usage_runs": sum(row["usage_runs"] for row in rows),
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "reasoning_tokens": sum(row["reasoning_tokens"] for row in rows),
        "total_tokens": sum(row["total_tokens"] for row in rows),
    }


def _format_history_period(period):
    if not _has_history_period(period or {}):
        return None
    start = _format_period_display(period.get("from")) or "beginning"
    end = _format_period_display(period.get("to")) or "now"
    return f"Period: {start} -> {end}"


def _format_period_display(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_history_summary(entries, period=None, use_color=False, active_sessions=None):
    from .cli_render import _format_relative_age, _pad_table

    active_sessions = active_sessions or set()
    summary = _summarize_history(entries)
    if not summary:
        return "No launch history for this period." if _has_history_period(period or {}) else "No launch history."
    rows = [[_style(value, "1", use_color) for value in ["SESSION", "PROV.", "LAUNCHES", "OK", "FAIL", "TIME", "LAST"]]]
    for row in summary:
        session_name = row["session_name"]
        display_name = f"{session_name}*" if session_name in active_sessions else session_name
        rows.append([
            _style(display_name, "36", use_color),
            _dim(row["provider"], use_color),
            _style(str(row["launches"]), "1", use_color),
            _style(str(row["successes"]), "32" if row["successes"] else "2", use_color),
            _style(str(row["failures"]), "31" if row["failures"] else "2", use_color),
            _style(_format_duration_ms(row["duration_ms"]), "33" if row["duration_ms"] else "2", use_color),
            _dim(_format_relative_age(row.get("last_started_at")), use_color),
        ])
    lines = [_style("Assistant time:", "1", use_color)]
    period_line = _format_history_period(period or {})
    if period_line:
        lines.extend([_dim(period_line, use_color), ""])
    lines.append(_pad_table(rows))
    return "\n".join(lines)


def _format_history(entries, use_color=False, active_sessions=None):
    from .cli_render import _format_relative_age, _pad_table

    active_sessions = active_sessions or set()
    if not entries:
        return "No launch history."
    rows = [[_style(value, "1", use_color) for value in ["SESSION", "PROV.", "RESULT", "DURATION", "WHEN", "TRANSCRIPT"]]]
    for entry in entries:
        transcript_path = entry.get("transcript_path")
        session_name = entry.get("session_name") or "-"
        display_name = f"{session_name}*" if session_name in active_sessions else session_name
        status = entry.get("status") or "-"
        status_color = "32" if status == "success" else "31" if status == "failed" else "2"
        rows.append([
            _style(display_name, "36", use_color),
            _dim(entry.get("provider") or "-", use_color),
            _style(status, status_color, use_color),
            _style(_format_duration_ms(entry.get("duration_ms")), "33" if entry.get("duration_ms") else "2", use_color),
            _dim(_format_relative_age(entry.get("started_at")), use_color),
            _dim(os.path.basename(transcript_path) if transcript_path else "-", use_color),
        ])
    return "\n".join([
        _style("Recent launches:", "1", use_color),
        _pad_table(rows),
        "",
        _dim("Full transcript paths and cwd are available with --json.", use_color),
    ])


def _format_token_count(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return "-"
    if amount >= 1000000:
        return f"{amount / 1000000:.1f}M"
    if amount >= 1000:
        return f"{amount / 1000:.1f}K"
    return str(amount)


def _format_stats(rows, totals, period=None, use_color=False, active_sessions=None):
    from .cli_render import _format_relative_age, _pad_table

    active_sessions = active_sessions or set()
    if not rows:
        return "No launch stats for this period." if _has_history_period(period or {}) else "No launch stats."
    table = [[_style(value, "1", use_color) for value in [
        "SESSION", "PROV.", "RUNS", "USAGE", "IN", "OUT", "REASON", "TOTAL", "TIME", "LAST"
    ]]]
    for row in rows:
        session_name = row["session_name"]
        display_name = f"{session_name}*" if session_name in active_sessions else session_name
        table.append([
            _style(display_name, "36", use_color),
            _dim(row["provider"], use_color),
            _style(str(row["launches"]), "1", use_color),
            _style(str(row["usage_runs"]), "32" if row["usage_runs"] else "2", use_color),
            _style(_format_token_count(row["input_tokens"]), "96" if row["input_tokens"] else "2", use_color),
            _style(_format_token_count(row["output_tokens"]), "96" if row["output_tokens"] else "2", use_color),
            _style(_format_token_count(row["reasoning_tokens"]), "95" if row["reasoning_tokens"] else "2", use_color),
            _style(_format_token_count(row["total_tokens"]), "1;96" if row["total_tokens"] else "2", use_color),
            _style(_format_duration_ms(row["duration_ms"]), "33" if row["duration_ms"] else "2", use_color),
            _dim(_format_relative_age(row.get("last_started_at")), use_color),
        ])
    lines = [_style("Assistant stats:", "1", use_color)]
    period_line = _format_history_period(period or {})
    if period_line:
        lines.extend([_dim(period_line, use_color), ""])
    lines.append(_pad_table(table))
    lines.extend([
        "",
        _dim(
            "Totals: "
            f"{totals['launches']} runs, {totals['usage_runs']} with usage, "
            f"{_format_token_count(totals['total_tokens'])} tokens, "
            f"{_format_duration_ms(totals['duration_ms'])}.",
            use_color,
        ),
    ])
    return "\n".join(lines)


def _active_session_names(ctx):
    return {
        row["name"]
        for row in ctx["service"]["format_list_rows"]()
        if row.get("active")
    }


def _apply_launch_settings(parsed, ctx, action="set"):
    targets = _resolve_bulk_launch_targets(parsed, ctx["service"])
    sessions = [
        ctx["service"]["set_launch_settings"](session["name"], parsed["settings"])
        for session in targets
    ]
    if len(sessions) == 1:
        session = sessions[0]
        message = f"Updated launch settings for {session['name']}"
    else:
        message = f"Updated launch settings for {len(sessions)} sessions: {_format_bulk_launch_summary(sessions)}"
    if parsed["json"]:
        payload = _json_success(
            action,
            message,
            updated_count=len(sessions),
            session=sessions[0] if len(sessions) == 1 else None,
            sessions=sessions,
            launch=sessions[0].get("launch") or {} if len(sessions) == 1 else None,
        )
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    if len(sessions) == 1:
        ctx["out"](f"{_format_launch_config(sessions[0], ctx['use_color'])}\n")
    return 0


def _clear_launch_settings(parsed, ctx, action="unset"):
    targets = _resolve_bulk_launch_targets(parsed, ctx["service"])
    sessions = [
        ctx["service"]["unset_launch_settings"](session["name"], parsed["keys"])
        for session in targets
    ]
    if len(sessions) == 1:
        session = sessions[0]
        message = f"Cleared launch settings for {session['name']}"
    else:
        message = f"Cleared launch settings for {len(sessions)} sessions: {_format_bulk_launch_summary(sessions)}"
    if parsed["json"]:
        payload = _json_success(
            action,
            message,
            updated_count=len(sessions),
            session=sessions[0] if len(sessions) == 1 else None,
            sessions=sessions,
            launch=sessions[0].get("launch") or {} if len(sessions) == 1 else None,
        )
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    if len(sessions) == 1:
        ctx["out"](f"{_format_launch_config(sessions[0], ctx['use_color'])}\n")
    return 0


def handle_set(rest, ctx):
    return _apply_launch_settings(_parse_set_args(rest), ctx)


def handle_unset(rest, ctx):
    return _clear_launch_settings(_parse_unset_args(rest), ctx)


def handle_launch_setting_alias(kind, rest, ctx):
    parsed = _parse_launch_setting_alias_args(kind, rest)
    if parsed.get("settings"):
        return _apply_launch_settings(parsed, ctx, action=kind)
    return _clear_launch_settings(parsed, ctx, action=kind)


def handle_config(rest, ctx):
    parsed = _parse_config_args(rest)
    session = ctx["service"]["get_session"](parsed["name"])
    if not session:
        raise CdxError(
            f"Unknown session: {parsed['name']}. Run cdx configs to inspect existing sessions or "
            f"cdx add {parsed['name']} to create it."
        )
    message = f"Launch settings for {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("config", message, session=session, launch=session.get("launch") or {}))
        return 0
    ctx["out"](f"{_format_launch_config(session, ctx['use_color'])}\n")
    return 0


def handle_configs(rest, ctx):
    parsed = _parse_configs_args(rest)
    sessions = ctx["service"]["list_sessions"]()
    message = f"Listed launch settings for {len(sessions)} session{'s' if len(sessions) != 1 else ''}"
    if parsed["json"]:
        _write_json(ctx, _json_success("configs", message, count=len(sessions), sessions=sessions))
        return 0
    ctx["out"](f"{_format_launch_configs(sessions, ctx['use_color'])}\n")
    return 0


def handle_history(rest, ctx):
    now_fn = ctx["options"].get("now") or time.time
    now = datetime.fromtimestamp(now_fn()).astimezone()
    parsed = _parse_history_args(rest, now=now)
    has_period = _has_history_period(parsed["period"])
    limit = 0 if parsed["summary"] or has_period else parsed["limit"]
    entries = ctx["service"]["get_launch_history"](parsed["name"], limit=limit)
    entries = _filter_history_period(entries, parsed["period"])
    if has_period and not parsed["summary"]:
        entries = entries[:parsed["limit"]]
    message = (
        f"Listed launch history for {parsed['name']}"
        if parsed["name"]
        else "Listed launch history"
    )
    if parsed["json"]:
        payload = {"history": entries, "period": _public_history_period(parsed["period"])}
        if parsed["summary"]:
            payload["summary"] = _summarize_history(entries)
        _write_json(ctx, _json_success("history", message, **payload))
        return 0
    active_sessions = _active_session_names(ctx)
    if parsed["summary"]:
        ctx["out"](f"{_format_history_summary(entries, period=parsed['period'], use_color=ctx['use_color'], active_sessions=active_sessions)}\n")
        return 0
    ctx["out"](f"{_format_history(entries, use_color=ctx['use_color'], active_sessions=active_sessions)}\n")
    return 0


def handle_stats(rest, ctx):
    now_fn = ctx["options"].get("now") or time.time
    now = datetime.fromtimestamp(now_fn()).astimezone()
    parsed = _parse_stats_args(rest, now=now)
    entries = ctx["service"]["get_launch_history"](parsed["name"], limit=0)
    entries = _filter_history_period(entries, parsed["period"])
    rows = _summarize_stats(entries)
    totals = _stats_totals(rows)
    message = (
        f"Calculated stats for {parsed['name']}"
        if parsed["name"]
        else "Calculated stats"
    )
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "stats",
            message,
            period=_public_history_period(parsed["period"]),
            stats=rows,
            totals=totals,
        ))
        return 0
    active_sessions = _active_session_names(ctx)
    ctx["out"](f"{_format_stats(rows, totals, period=parsed['period'], use_color=ctx['use_color'], active_sessions=active_sessions)}\n")
    return 0


def _resolve_last_launch_session(ctx):
    for entry in ctx["service"]["get_launch_history"](limit=0):
        name = entry.get("session_name")
        if not name:
            continue
        session = ctx["service"]["get_session"](name)
        if session:
            return session
    raise CdxError("No launch history yet. Run cdx <name> first.")


def handle_last(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if args:
        raise CdxError(LAST_USAGE)
    session = _resolve_last_launch_session(ctx)
    if not json_flag:
        message = f"Launching last session: {session['name']}"
        ctx["out"](f"{_info(message, ctx['use_color'])}\n")
    return handle_launch(session["name"], ctx)


def handle_notify(rest, ctx):
    parsed = parse_notify_args(rest)

    def notifier(title, message):
        send_desktop_notification(
            title,
            message,
            spawn_sync=ctx.get("spawn_sync"),
            env=ctx.get("env"),
        )

    if parsed["schedule"]:
        event = resolve_notify_event(
            ctx["service"]["get_status_rows"](
                progress_callback=None if parsed["json"] else _make_notify_progress(ctx),
                force_refresh=parsed.get("refresh", False),
            ),
            parsed,
            (ctx["options"].get("now") or time.time)(),
        )
        if event["ready"]:
            notifier(event["title"], event["message"])
            schedule = {
                "scheduled": False,
                "backend": "immediate",
                "message": event["message"],
                "target_timestamp": event.get("target_timestamp"),
            }
        else:
            schedule = schedule_notification_event(
                ctx["service"]["base_dir"],
                parsed,
                event,
                spawn_sync=ctx.get("spawn_sync"),
                env=ctx.get("env"),
                now_fn=ctx["options"].get("now"),
            )
        if parsed["json"]:
            _write_json(ctx, _json_success("notify", "Scheduled notification event", event=event, schedule=schedule))
        else:
            ctx["out"](f"{format_scheduled_notification(schedule)}\n")
        return 0

    event = wait_for_notification_event(
        ctx["service"],
        parsed,
        notifier=notifier,
        sleep_fn=ctx["options"].get("sleep"),
        now_fn=ctx["options"].get("now"),
        progress_callback=None if parsed["json"] else _make_notify_progress(ctx),
    )
    if parsed["json"]:
        _write_json(ctx, _json_success("notify", "Resolved notification event", event=event))
    else:
        ctx["out"](f"{format_notify_event(event)}\n")
    return 0


def handle_context(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if not args:
        args = ["show"]
    action = args[0]
    base_dir = ctx["service"]["base_dir"]
    cwd = ctx.get("cwd")

    if action == "show":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        content = read_context(base_dir, cwd)
        payload = {
            "path": get_context_path(base_dir, cwd),
            "exists": bool(content.strip()),
            "content": content,
        }
        if json_flag:
            _write_json(ctx, _json_success("context.show", "Loaded shared context", context=payload))
            return 0
        if content.strip():
            ctx["out"](content if content.endswith("\n") else f"{content}\n")
        else:
            ctx["out"](f"{_dim('No shared context for this workspace. Run: cdx context init or cdx context set <text>', ctx['use_color'])}\n")
        return 0

    if action == "path":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        path = get_context_path(base_dir, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.path", "Resolved shared context path", path=path))
            return 0
        ctx["out"](f"{path}\n")
        return 0

    if action == "init":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = init_context(base_dir, cwd)
        message = "Created shared context" if result.get("created") else "Shared context already exists"
        if json_flag:
            _write_json(ctx, _json_success("context.init", message, context=result))
            return 0
        text = f"{message}: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "edit":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = edit_context(
            base_dir,
            cwd,
            env=ctx.get("env"),
            spawn_sync=ctx.get("spawn_sync"),
        )
        if json_flag:
            _write_json(ctx, _json_success("context.edit", "Edited shared context", context=result))
            return 0
        text = f"Edited shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "clear":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = clear_context(base_dir, cwd)
        message = "Cleared shared context" if result["removed"] else "No shared context to clear"
        if json_flag:
            _write_json(ctx, _json_success("context.clear", message, context=result))
            return 0
        ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        return 0

    if action == "set":
        content_args = args[1:]
        if content_args:
            content = " ".join(content_args)
        else:
            stdin = ctx["options"].get("stdin_data")
            if stdin is None and not ctx.get("stdin_is_tty"):
                stdin = sys.stdin.read()
            if stdin is None:
                raise CdxError("Usage: cdx context set <text> [--json]")
            content = stdin
        result = write_context(base_dir, content, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.set", "Saved shared context", context=result))
            return 0
        text = f"Saved shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "append":
        note = " ".join(args[1:])
        if not note.strip():
            raise CdxError("Usage: cdx context append <text> [--json]")
        result = append_context(base_dir, note, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.append", "Appended shared context", context=result))
            return 0
        text = f"Appended shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    raise CdxError(CONTEXT_USAGE)


def _parse_memory_args(rest):
    json_flag, args = _parse_json_flag(rest)
    scope = "current"
    project = None
    cleaned = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--global":
            if scope != "current":
                raise CdxError(MEMORY_USAGE)
            scope = "global"
            index += 1
            continue
        if arg == "--project":
            if scope != "current" or index + 1 >= len(args) or not args[index + 1].strip():
                raise CdxError(MEMORY_USAGE)
            scope = "project"
            project = args[index + 1].strip()
            index += 2
            continue
        if arg.startswith("--project="):
            if scope != "current":
                raise CdxError(MEMORY_USAGE)
            project = arg.split("=", 1)[1].strip()
            if not project:
                raise CdxError(MEMORY_USAGE)
            scope = "project"
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    if not cleaned:
        cleaned = ["show"]
    if cleaned[0] == "view":
        cleaned[0] = "show"
    return json_flag, scope, project, cleaned


def _memory_target(base_dir, cwd, scope, project):
    if scope == "global":
        return {"scope": "global", "path": get_global_context_path(base_dir)}
    if scope == "project":
        if os.path.exists(project):
            return {
                "scope": "project",
                "project": project,
                "project_kind": "path",
                "path": get_context_path(base_dir, project),
            }
        return {
            "scope": "project",
            "project": project,
            "project_kind": "name",
            "path": get_named_project_context_path(base_dir, project),
        }
    return {"scope": "current", "path": get_context_path(base_dir, cwd)}


def _memory_payload(target, content=None):
    payload = {
        "scope": target["scope"],
        "path": target["path"],
        "exists": os.path.isfile(target["path"]),
    }
    if target.get("project") is not None:
        payload["project"] = target["project"]
        payload["project_kind"] = target.get("project_kind")
    if payload["exists"]:
        payload["bytes"] = os.path.getsize(target["path"])
    if content is not None:
        payload["content"] = content
    return payload


def _list_memory_entries(base_dir, cwd):
    entries = []
    global_path = get_global_context_path(base_dir)
    if os.path.isfile(global_path):
        entries.append({"scope": "global", "path": global_path, "bytes": os.path.getsize(global_path)})
    entries.extend(list_named_project_contexts(base_dir))
    current_path = get_context_path(base_dir, cwd)
    if os.path.isfile(current_path):
        entries.append({"scope": "current", "path": current_path, "bytes": os.path.getsize(current_path)})
    return entries


def handle_memory(rest, ctx):
    json_flag, scope, project, args = _parse_memory_args(rest)
    action = args[0]
    base_dir = ctx["service"]["base_dir"]
    cwd = ctx.get("cwd")

    if action == "list":
        if len(args) != 1 or scope != "current":
            raise CdxError(MEMORY_USAGE)
        entries = _list_memory_entries(base_dir, cwd)
        if json_flag:
            _write_json(ctx, _json_success("memory.list", "Listed memory scopes", memories=entries))
            return 0
        if not entries:
            ctx["out"](f"{_dim('No cdx memory files found.', ctx['use_color'])}\n")
            return 0
        rows = [["SCOPE", "PROJECT", "SIZE", "PATH"]]
        for entry in entries:
            rows.append([
                entry["scope"],
                entry.get("project") or "-",
                _format_bytes(entry.get("bytes") or 0),
                entry["path"],
            ])
        ctx["out"](_pad_table(rows) + "\n")
        return 0

    target = _memory_target(base_dir, cwd, scope, project)
    path = target["path"]

    if action == "show":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        content = read_context_path(path)
        payload = _memory_payload(target, content=content)
        if json_flag:
            _write_json(ctx, _json_success("memory.show", "Loaded memory", memory=payload))
            return 0
        if content.strip():
            ctx["out"](content if content.endswith("\n") else f"{content}\n")
        else:
            ctx["out"](f"{_dim('No memory for this scope. Run: cdx memory append <text>', ctx['use_color'])}\n")
        return 0

    if action == "path":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        if json_flag:
            _write_json(ctx, _json_success("memory.path", "Resolved memory path", memory=_memory_payload(target)))
            return 0
        ctx["out"](f"{path}\n")
        return 0

    if action == "init":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        result = init_context_path(path)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        message = "Created memory" if result.get("created") else "Memory already exists"
        if json_flag:
            _write_json(ctx, _json_success("memory.init", message, memory=result))
            return 0
        ctx["out"](f"{_success(f'{message}: {path}', ctx['use_color'])}\n")
        return 0

    if action == "edit":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        result = edit_context_path(path, env=ctx.get("env"), spawn_sync=ctx.get("spawn_sync"))
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        if json_flag:
            _write_json(ctx, _json_success("memory.edit", "Edited memory", memory=result))
            return 0
        ctx["out"](f"{_success(f'Edited memory: {path}', ctx['use_color'])}\n")
        return 0

    if action == "clear":
        if len(args) != 1:
            raise CdxError(MEMORY_USAGE)
        result = clear_context_path(path)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        message = "Cleared memory" if result["removed"] else "No memory to clear"
        if json_flag:
            _write_json(ctx, _json_success("memory.clear", message, memory=result))
            return 0
        ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        return 0

    if action == "set":
        content_args = args[1:]
        if content_args:
            content = " ".join(content_args)
        else:
            stdin = ctx["options"].get("stdin_data")
            if stdin is None and not ctx.get("stdin_is_tty"):
                stdin = sys.stdin.read()
            if stdin is None:
                raise CdxError("Usage: cdx memory set <text> [--json]")
            content = stdin
        result = write_context_path(path, content)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        if json_flag:
            _write_json(ctx, _json_success("memory.set", "Saved memory", memory=result))
            return 0
        ctx["out"](f"{_success(f'Saved memory: {path}', ctx['use_color'])}\n")
        return 0

    if action == "append":
        note = " ".join(args[1:])
        result = append_context_path(path, note)
        result = {**result, **{key: value for key, value in target.items() if key != "path"}}
        if json_flag:
            _write_json(ctx, _json_success("memory.append", "Appended memory", memory=result))
            return 0
        ctx["out"](f"{_success(f'Appended memory: {path}', ctx['use_color'])}\n")
        return 0

    raise CdxError(MEMORY_USAGE)


def handle_status(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--small": {"key": "small", "type": "bool", "default": False},
        "-s": {"key": "small", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--cached": {"key": "cached", "type": "bool", "default": False},
        "--timeout": {"key": "timeout", "type": "str", "default": None, "transform": lambda value: _parse_timeout_seconds(value, STATUS_USAGE)},
    }, STATUS_USAGE, positionals_key="args", max_positionals=1)
    if parsed["json"] and parsed["small"]:
        raise CdxError(STATUS_USAGE)
    if parsed["refresh"] and parsed["cached"]:
        raise CdxError(STATUS_USAGE)
    args = parsed["args"]
    if len(args) == 1 and parsed["small"]:
        raise CdxError(STATUS_USAGE)

    auth_refresh = (
        {"errors": []}
        if parsed["cached"]
        else _refresh_claude_auth_states(
            ctx["service"],
            target_names=args if len(args) == 1 else None,
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
        )
    )
    warnings = [
        {
            "code": "claude_auth_probe_failed",
            "session": item.get("session") or "unknown",
            "message": item.get("error") or "unknown error",
        }
        for item in auth_refresh.get("errors", [])
    ]
    refresh_result = (
        {"errors": []}
        if parsed["cached"]
        else _refresh_claude_sessions(
            ctx["service"],
            ctx.get("refresh_fn"),
            target_names=args if len(args) == 1 else None,
            force=parsed["refresh"],
        )
    )
    refresh_errors = [
        {
            "session": item.get("session"),
            "error": str(item.get("error")),
        }
        for item in refresh_result.get("errors", [])
    ]
    status_progress = None if parsed["json"] else _make_status_progress(ctx)
    if len(args) == 1:
        row = ctx["service"]["get_status_row"](
            args[0],
            progress_callback=status_progress,
            force_refresh=parsed["refresh"],
            cache_only=parsed["cached"],
            status_timeout_seconds=parsed["timeout"],
        )
        output_warnings = [
            *warnings,
            *_refresh_warning_payloads(refresh_errors, [row]),
            *_update_notice_warnings(ctx),
        ]
        if parsed["json"]:
            _write_json(ctx, _json_success("status", f"Collected status for {args[0]}", warnings=output_warnings, session=row))
            return 0
        ctx["out"](f"{_format_status_detail(row, use_color=ctx['use_color'])}\n")
        _write_refresh_warnings(refresh_errors, ctx, rows=[row])
        _write_update_notice(ctx)
        return 0

    rows = ctx["service"]["get_status_rows"](
        progress_callback=status_progress,
        force_refresh=parsed["refresh"],
        cache_only=parsed["cached"],
        status_timeout_seconds=parsed["timeout"],
    )
    output_warnings = [
        *warnings,
        *_refresh_warning_payloads(refresh_errors, rows),
        *_update_notice_warnings(ctx),
    ]
    if parsed["json"]:
        _write_json(ctx, _json_success("status", "Collected session status rows", warnings=output_warnings, rows=rows))
        return 0
    ctx["out"](f"{_format_status_rows(rows, use_color=ctx['use_color'], small=parsed['small'])}\n")
    _write_refresh_warnings(refresh_errors, ctx, rows=rows)
    _write_update_notice(ctx)
    return 0


def handle_reset(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--yes": {"key": "yes", "type": "bool", "default": False},
    }, "Usage: cdx reset <name> [--yes] [--json]", positionals_key="args", max_positionals=1)
    if len(parsed["args"]) != 1:
        raise CdxError("Usage: cdx reset <name> [--yes] [--json]")
    name = parsed["args"][0]
    session = ctx["service"]["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    if session["provider"] != PROVIDER_CODEX:
        raise CdxError("Banked rate-limit resets are only available for Codex sessions.")

    status = ctx["service"]["get_status_row"](name, force_refresh=True)
    if status.get("reset_credits_available") == 0:
        raise CdxError(f"No banked Codex reset is available for {name}.")
    if not parsed["yes"]:
        confirm_fn = ctx["options"].get("confirmReset")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, name)
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Reset activation requires an interactive terminal or --yes in non-interactive mode.")
        else:
            confirmed = _confirm_reset(name)
        if not confirmed:
            if parsed["json"]:
                _write_json(ctx, _json_success("reset", "Cancelled.", cancelled=True, session=name))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0

    credit_rows = status.get("reset_credits") or []
    credit_id = credit_rows[0].get("id") if credit_rows else None
    consumer = ctx["options"].get("consumeCodexReset") or consume_codex_rate_limit_reset_credit
    result = consumer(
        session,
        ctx["options"].get("resetIdempotencyKey") or str(uuid.uuid4()),
        credit_id=credit_id,
    )
    if not result.get("ok"):
        if result.get("reason") == "reset_consume_failed":
            raise CdxError(
                f"Unable to activate Codex reset for {name}. "
                "The installed Codex version or account may not support reset activation."
            )
        raise CdxError(f"Unable to activate Codex reset for {name}: {result.get('reason') or 'unknown error'}")
    outcome = result.get("outcome")
    if outcome == "noCredit":
        raise CdxError(f"No banked Codex reset is available for {name}.")
    if outcome == "nothingToReset":
        raise CdxError(f"No current Codex rate-limit window is eligible for reset on {name}.")
    if outcome not in ("reset", "alreadyRedeemed"):
        raise CdxError(f"Unexpected Codex reset outcome for {name}: {outcome or 'missing'}")
    refreshed = ctx["service"]["get_status_row"](name, force_refresh=True)
    message = f"Activated banked Codex reset for {name}"
    if parsed["json"]:
        _write_json(ctx, _json_success("reset", message, cancelled=False, outcome=outcome, session=refreshed))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def _refresh_claude_auth_states(service, target_names=None, spawn_sync=None, env_override=None):
    target_names = set(target_names or [])
    errors = []
    updated = []
    for session in service["list_sessions"]():
        if session["provider"] != PROVIDER_CLAUDE:
            continue
        if session.get("enabled", True) is False:
            continue
        if target_names and session["name"] not in target_names:
            continue
        if (session.get("auth") or {}).get("status") not in ("authenticated", "logged_out"):
            continue
        try:
            auth_status = _probe_provider_auth_status(
                session,
                spawn_sync=spawn_sync,
                env_override=env_override,
            )
            if auth_status == AUTH_PROBE_DEGRADED:
                errors.append({
                    "session": session["name"],
                    "error": "Auth probe timed out; authentication status is degraded.",
                })
                continue
            now = _local_now_iso()
            service["update_auth_state"](session["name"], lambda auth, auth_status=auth_status, now=now: {
                **auth,
                "status": "authenticated" if auth_status == AUTH_PROBE_AUTHENTICATED else "logged_out",
                "lastCheckedAt": now,
                **({"lastAuthenticatedAt": now} if auth_status == AUTH_PROBE_AUTHENTICATED else {}),
            })
            updated.append(session["name"])
        except Exception as error:
            errors.append({"session": session["name"], "error": str(error)})
    return {"updated": updated, "errors": errors}


def _rows_by_session(rows):
    return {
        row.get("session_name"): row
        for row in (rows or [])
        if row.get("session_name")
    }


def _is_invalid_claude_usage_auth(error):
    text = str(error or "").lower()
    return "http 401" in text and "invalid authentication credentials" in text


def _has_valid_local_claude_auth(item, rows_by_name):
    session = item.get("session")
    row = rows_by_name.get(session)
    return bool(row and row.get("provider") == PROVIDER_CLAUDE and row.get("auth_status") == "authenticated")


def _refresh_warning_payloads(refresh_errors, rows=None):
    rows_by_name = _rows_by_session(rows)
    warnings = []
    for item in refresh_errors:
        session = item.get("session") or "unknown"
        error = item.get("error") or "unknown error"
        warning = {
            "code": "claude_refresh_failed",
            "session": session,
            "message": error,
        }
        if _is_invalid_claude_usage_auth(error) and _has_valid_local_claude_auth(item, rows_by_name):
            warning.update({
                "auth_status": "authenticated",
                "status_freshness": "stale",
                "message": (
                    "Claude quota refresh failed, but local Claude auth is still valid; "
                    f"cached quota may be stale. Original error: {error}"
                ),
            })
        warnings.append(warning)
    return warnings


def _format_refresh_warning(item, rows_by_name):
    session = item.get("session") or "unknown"
    error = item.get("error") or "unknown error"
    if _is_invalid_claude_usage_auth(error) and _has_valid_local_claude_auth(item, rows_by_name):
        return (
            f"Warning: Claude quota refresh failed for {session}, but local auth is still valid; "
            f"cached quota may be stale. ({error})"
        )
    return f"Warning: Claude refresh failed for {session}: {error}"


def _write_refresh_warnings(refresh_errors, ctx, stream="out", rows=None):
    write = ctx["err"] if stream == "err" and "err" in ctx else ctx["out"]
    rows_by_name = _rows_by_session(rows)
    for item in refresh_errors:
        write(f"{_warn(_format_refresh_warning(item, rows_by_name), ctx['use_color'])}\n")


def handle_export(rest, ctx):
    parsed = _parse_export_args(rest)
    passphrase = None
    if parsed["include_auth"]:
        passphrase = _resolve_bundle_passphrase(
            ctx,
            parsed["passphrase_env"],
            "Bundle passphrase: ",
            confirm=True,
            use_stdin=parsed["passphrase_stdin"],
        )
    result = ctx["service"]["export_bundle"](
        parsed["file_path"],
        include_auth=parsed["include_auth"],
        session_names=parsed["session_names"],
        passphrase=passphrase,
        force=parsed["force"],
        progress_callback=None if parsed["json"] else _make_export_progress(ctx),
    )
    session_count = len(result["session_names"])
    auth_suffix = " with auth" if result["include_auth"] else ""
    message = f"Exported {session_count} session{'s' if session_count != 1 else ''}{auth_suffix} to {result['path']}"
    payload = _json_success(
        "export",
        message,
        bundle=result,
    )
    if parsed["json"]:
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    ctx["out"](f"{_format_export_report(result)}\n")
    return 0


def handle_import(rest, ctx):
    parsed = _parse_import_args(rest)
    passphrase = None
    try:
        with open(parsed["file_path"], "rb") as handle:
            meta = read_bundle_meta(handle.read())
    except OSError as error:
        raise CdxError(f"Bundle file not found: {parsed['file_path']}") from error
    if meta.get("encrypted"):
        passphrase = _resolve_bundle_passphrase(
            ctx,
            parsed["passphrase_env"],
            "Bundle passphrase: ",
            confirm=False,
            use_stdin=parsed["passphrase_stdin"],
        )
    result = ctx["service"]["import_bundle"](
        parsed["file_path"],
        passphrase=passphrase,
        session_names=parsed["session_names"],
        force=parsed["force"],
        merge=parsed["merge"],
        allow_authless_force=parsed["allow_authless_force"],
    )
    session_count = len(result["session_names"])
    auth_suffix = " with auth" if result["include_auth"] else ""
    message = f"Imported {session_count} session{'s' if session_count != 1 else ''}{auth_suffix} from {result['path']}"
    payload = _json_success(
        "import",
        message,
        bundle=result,
    )
    if parsed["json"]:
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_login(rest, ctx):
    rest = [arg for arg in rest if arg != "--setup-token"]  # accepted for back-compat; setup-token is now the default for Claude
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx login <name> [--json]")
    if not ctx["stdin_is_tty"]:
        raise CdxError("Login requires an interactive terminal.")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session["provider"] == PROVIDER_CLAUDE:
        # ponytail: setup-token mints a ~1yr token; claude login mints a ~daily one that forces reconnects
        _bootstrap_claude_setup_token(session, ctx)
    else:
        _run_interactive_provider_command(
            session, "login", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
            signal_emitter=ctx.get("signal_emitter")
        )
    auth_probe = _ensure_session_authentication(
        session,
        ctx["service"],
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
        behavior="probe-only",
        trust_local_credentials=False,
    )
    if not auth_probe.get("authenticated"):
        raise CdxError(
            f"Login command completed, but session {session['name']} is still not authenticated."
        )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](args[0], lambda auth: {
        **auth, "status": "authenticated",
        "lastCheckedAt": now, "lastAuthenticatedAt": now,
    })
    message = f"Reauthenticated session {session['name']} ({session['provider']})"
    if json_flag:
        _write_json(ctx, _json_success("login", message, session=ctx["service"]["get_session"](session["name"])))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_logout(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx logout <name> [--json]")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session["provider"] == PROVIDER_ANTIGRAVITY:
        raise CdxError("Antigravity logout is managed inside agy. Launch the session and run /logout.")
    if session["provider"] == PROVIDER_OLLAMA:
        raise CdxError("Ollama sessions do not use cdx-managed authentication.")
    _run_interactive_provider_command(
        session, "logout", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter")
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](args[0], lambda auth: {
        **auth, "status": "logged_out",
        "lastCheckedAt": now, "lastLoggedOutAt": now,
    })
    message = f"Logged out session {session['name']} ({session['provider']})"
    if json_flag:
        _write_json(ctx, _json_success("logout", message, session=ctx["service"]["get_session"](session["name"])))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def _resume_capability_for_session(session, ctx):
    capability = get_resume_capability(session, cwd=ctx.get("cwd") or os.getcwd())
    return {
        "session": session["name"],
        "provider": session["provider"],
        "resumable": bool(capability.get("resumable")),
        "strategy": capability.get("strategy"),
        "reason": capability.get("reason"),
        "command_preview": capability.get("command_preview") or [],
    }


def _format_resume_capability(capability, use_color=False):
    name = capability["session"]
    provider = capability["provider"]
    if capability["resumable"]:
        preview = shlex.join(capability.get("command_preview") or [])
        detail = f"({provider}, {capability['strategy']})"
        return (
            f"{_success(f'{name} can resume', use_color)} "
            f"{_dim(detail, use_color)}\n"
            f"{_dim(preview, use_color)}"
        )
    reason = capability.get("reason") or "not_supported"
    return (
        f"{_warn(f'{name} cannot resume', use_color)} "
        f"{_dim(f'({provider}, {reason})', use_color)}"
    )


def handle_can_resume(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError(CAN_RESUME_USAGE)
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session.get("enabled", True) is False:
        capability = {
            "session": session["name"],
            "provider": session["provider"],
            "resumable": False,
            "strategy": "session_disabled",
            "reason": "session_disabled",
            "command_preview": [],
        }
    else:
        capability = _resume_capability_for_session(session, ctx)
    if json_flag:
        _write_json(ctx, {
            "schema_version": API_SCHEMA_VERSION,
            "ok": True,
            **capability,
        })
        return 0
    ctx["out"](f"{_format_resume_capability(capability, ctx['use_color'])}\n")
    return 0


def handle_resume(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError(RESUME_USAGE)
    return handle_launch(args[0], ctx, resume=True, force_json=json_flag)


def _warn_if_session_already_running(name, ctx):
    # ponytail: concurrent sessions on one profile share its single OAuth
    # .credentials.json; both refresh near token expiry and the rotated refresh
    # token invalidates the other session -> surprise logout. Warn before adding
    # a second live session on the same profile.
    active = ctx["service"].get("active_session_runtime")
    runtime = active(name) if active else None
    if not runtime:
        return
    pid = runtime.get("pid")
    ctx["out"](f"{_warn(f'A session named {name} is already running (pid {pid}).', ctx['use_color'])}\n")
    ctx["out"](
        f"{_dim('Two sessions on one profile share its login and can log each other out. Use a different profile instead.', ctx['use_color'])}\n"
    )
    if not ctx["stdin_is_tty"]:
        return
    answer = input(f"Launch a second {name} session anyway? [y/N] ")
    if answer.strip().lower() not in ("y", "yes"):
        raise CdxError("Launch cancelled.")


def handle_launch(command, ctx, initial_prompt=None, resume=False, force_json=None):
    json_flag = "--json" in ctx.get("raw_args", ctx["options"].get("raw_args", []))
    if force_json is not None:
        json_flag = force_json
    warnings = _update_notice_warnings(ctx)
    _warn_if_session_already_running(command, ctx)
    session = ctx["service"]["launch_session"](command)
    capability = _resume_capability_for_session(session, ctx) if resume else None
    if capability and not capability["resumable"]:
        raise CdxError(
            f"Provider {session['provider']} does not support native resume through cdx."
        )
    _ensure_session_authentication(
        session,
        ctx["service"],
        spawn=ctx.get("spawn"),
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
        stdin_is_tty=ctx["stdin_is_tty"],
        behavior="launch",
        signal_emitter=ctx.get("signal_emitter"),
        trust_local_credentials=False,
    )
    message = (
        f"Resuming {session['provider']} session {session['name']}"
        if resume else
        f"Launching {session['provider']} session {session['name']}"
    )
    if not json_flag:
        ctx["out"](f"{_info(message, ctx['use_color'])}\n")
        _write_update_notice(ctx)
    cwd = ctx.get("cwd") or os.getcwd()
    runtime_run_id = None

    def runtime_lifecycle(event, info):
        nonlocal runtime_run_id
        if event == "started":
            runtime = ctx["service"]["start_session_runtime"](session["name"], info)
            runtime_run_id = runtime.get("runId")
        elif event == "finished" and runtime_run_id:
            ctx["service"]["finish_session_runtime"](
                session["name"],
                runtime_run_id,
                {"status": "stopped", "returncode": info.get("returncode")},
            )

    try:
        run_info = _run_interactive_provider_command(
            session, "resume" if resume else "launch", spawn=ctx.get("spawn"), cwd=cwd, env_override=ctx.get("env"),
            signal_emitter=ctx.get("signal_emitter"), initial_prompt=initial_prompt,
            lifecycle_callback=runtime_lifecycle,
        )
    except CdxError as error:
        run_info = getattr(error, "run_info", {}) or {}
        if runtime_run_id:
            ctx["service"]["finish_session_runtime"](
                session["name"],
                runtime_run_id,
                {"status": "failed", "returncode": run_info.get("returncode")},
            )
        if run_info:
            ctx["service"]["record_launch_history"](session["name"], {
                "status": "failed",
                "cwd": cwd,
                "error": str(error),
                "exit_code": error.exit_code,
                **run_info,
            })
        raise
    ctx["service"]["record_launch_history"](session["name"], {
        "status": "success",
        "action": "resume" if resume else "launch",
        "cwd": cwd,
        "exit_code": 0,
        **run_info,
    })
    if json_flag:
        extra = {"session": ctx["service"]["get_session"](session["name"])}
        if capability:
            extra["resume"] = capability
        _write_json(ctx, _json_success("resume" if resume else "launch", message, warnings=warnings, **extra))
    return 0


def handle_handoff(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) not in (1, 2):
        raise CdxError(HANDOFF_USAGE)
    if len(args) == 1:
        name = args[0]
        session = ctx["service"]["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        install = install_context_for_session(ctx["service"]["base_dir"], session, ctx.get("cwd"))
        launch_prompt = _handoff_launch_prompt(session, install)
        if json_flag:
            _write_json(ctx, _json_success(
                "handoff",
                f"Installed shared context for {name}",
                context=install,
                launch_prompt=launch_prompt,
                session=session,
            ))
            return 0
        text = f"Shared context installed for {name}: {install['target_path']}"
        ctx["out"](f"{_info(text, ctx['use_color'])}\n")
        return handle_launch(name, ctx, initial_prompt=launch_prompt)

    source_name, target_name = args
    if source_name == target_name:
        raise CdxError("Source and target sessions must be different")
    source = ctx["service"]["get_session"](source_name)
    if not source:
        raise CdxError(f"Unknown session: {source_name}")
    target = ctx["service"]["get_session"](target_name)
    if not target:
        raise CdxError(f"Unknown session: {target_name}")
    transcript_path = _latest_handoff_transcript_path(source)
    if not transcript_path:
        raise CdxError(f"No transcript found for session: {source_name}")
    transcript, truncated = _read_handoff_transcript(transcript_path)
    context = _build_handoff_context(source, target, transcript_path, transcript, truncated=truncated)
    write_result = write_context(ctx["service"]["base_dir"], context, ctx.get("cwd"))
    install = install_context_for_session(ctx["service"]["base_dir"], target, ctx.get("cwd"))
    launch_prompt = _handoff_launch_prompt(target, install)
    if json_flag:
        _write_json(ctx, _json_success(
            "handoff",
            f"Prepared handoff from {source_name} to {target_name}",
            context=install,
            source_session=source,
            target_session=target,
            source_transcript=transcript_path,
            shared_context=write_result,
            launch_prompt=launch_prompt,
        ))
        return 0
    text = f"Handoff prepared from {source_name} to {target_name}: {install['target_path']}"
    ctx["out"](f"{_info(text, ctx['use_color'])}\n")
    return handle_launch(target_name, ctx, initial_prompt=launch_prompt)
