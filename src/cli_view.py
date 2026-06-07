import json

from .cli_render import _warn
from .errors import CdxError
from .logics_view import (
    LOGICS_MANAGER_INSTALL_HINT,
    build_viewer_diagnostics,
    missing_logics_manager_failure,
    resolve_logics_manager,
    run_logics_viewer,
)
from .update_check import check_logics_manager_for_update


VIEW_USAGE = "Usage: cdx view [--json]"
API_SCHEMA_VERSION = 1


def _json_success(action, message, warnings=None, **extra):
    payload = {
        "schema_version": API_SCHEMA_VERSION,
        "ok": True,
        "action": action,
        "message": message,
        "warnings": warnings or [],
    }
    payload.update(extra)
    return payload


def _write_json(ctx, payload):
    ctx["out"](f"{json.dumps(payload, indent=2)}\n")


def _update_notice_warnings(notices):
    warnings = []
    for notice in notices or []:
        if not notice:
            continue
        tool = notice.get("tool") or "logics-manager"
        current = notice.get("current_version")
        command = notice.get("update_command")
        message = f"Update available: {tool} {notice['latest_version']}"
        if current:
            message = f"{message} (current {current})"
        if command:
            message = f"{message}. Run: {command}"
        warnings.append({
            "code": f"{tool.replace('-', '_')}_update_available",
            "message": message,
            "tool": tool,
            "latest_version": notice["latest_version"],
            "current_version": current,
            "update_command": command,
            "url": notice.get("url"),
        })
    return warnings


def _logics_manager_update_notice(ctx, env):
    checker = ctx["options"].get("checkLogicsManagerForUpdate") or check_logics_manager_for_update
    return checker(
        ctx["service"]["base_dir"],
        env=env,
        now_fn=ctx["options"].get("now"),
        runner=ctx["options"].get("runLogicsVersionCheck"),
    )


def handle_view(rest, ctx):
    json_flag = "--json" in rest
    unknown = [arg for arg in rest if arg != "--json"]
    if unknown:
        raise CdxError(VIEW_USAGE)

    env = ctx.get("env")
    cwd = ctx.get("cwd")
    executable = resolve_logics_manager(env=env)
    update_notice = _logics_manager_update_notice(ctx, env) if executable else None
    failure = None if executable else missing_logics_manager_failure()
    diagnostics = build_viewer_diagnostics(executable, cwd, update_notice=update_notice, failure=failure)
    warnings = _update_notice_warnings([update_notice])

    if json_flag:
        _write_json(ctx, _json_success("view", "Collected Logics viewer diagnostics", warnings=warnings, viewer=diagnostics))
        return 0

    if not executable:
        raise CdxError(f"logics-manager is required for cdx view. {LOGICS_MANAGER_INSTALL_HINT}")

    for warning in warnings:
        ctx["out"](f"{_warn(warning['message'], ctx['use_color'])}\n")

    try:
        result = run_logics_viewer(executable, cwd, env=env, runner=ctx.get("spawn_sync"))
    except FileNotFoundError as error:
        raise CdxError(f"logics-manager is required for cdx view. {LOGICS_MANAGER_INSTALL_HINT}") from error
    returncode = getattr(result, "returncode", 0)
    if returncode not in (0, None):
        raise CdxError("logics-manager view failed.", exit_code=returncode)
    return 0
