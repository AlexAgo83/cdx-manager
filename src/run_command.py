import os
import sys

from .cli_args import ARG_CODE_INVALID_VALUE
from .errors import CdxArgumentError, CdxError
from .provider_runtime import headless_permission_disables_network
from .run_usage import empty_usage, extract_run_observation

PROMPT_STDIN = "-"


def read_run_prompt(parsed, stdin=None):
    if parsed.get("prompt") is not None:
        return parsed["prompt"]
    if parsed.get("prompt_file") == PROMPT_STDIN:
        stream = stdin if stdin is not None else sys.stdin
        if stream is None or getattr(stream, "isatty", lambda: False)():
            raise CdxArgumentError(
                "cdx run: --prompt-file - reads the prompt from standard input, but standard "
                "input is a terminal. Pipe the prompt in, or pass a file path.",
                code=ARG_CODE_INVALID_VALUE,
                arguments=["--prompt-file"],
            )
        return stream.read()
    try:
        with open(parsed["prompt_file"], encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise CdxError(f"Unable to read prompt file: {parsed['prompt_file']}") from error


def run_cdx_error_code(error):
    code = getattr(error, "code", None)
    if code:
        return code
    message = str(error)
    if message.startswith("Usage:"):
        return "invalid_request"
    if message.startswith("cdx run:"):
        return "invalid_request"
    if message.startswith("Invalid cwd:"):
        return "invalid_cwd"
    if message.startswith("Session is disabled:"):
        return "session_disabled"
    if "CLI not found on PATH" in message:
        return "provider_cli_not_found"
    if message.startswith("Failed to start "):
        return "provider_start_failed"
    if (
        message.startswith("Unsupported reasoning effort:")
        or message.startswith("Unsupported power:")
        or "--reasoning-effort and --power must match" in message
    ):
        return "invalid_reasoning_effort"
    return "cdx_error"


def run_conversation_id(session, run_info=None):
    if run_info is not None and "conversation_id" in run_info:
        return run_info["conversation_id"]
    if (session or {}).get("provider") == "codex" and not session.get("continue_run"):
        return None
    return ((session or {}).get("conversation") or {}).get("id")


def run_payload_reasoning_effort(parsed, session):
    launch = (session.get("launch") or {}) if session else {}
    return (
        parsed.get("reasoning_effort")
        or parsed.get("power")
        or launch.get("reasoning_effort")
        or launch.get("reasoningEffort")
        or launch.get("power")
        or ("low" if launch.get("fast") is True and launch.get("fastMode") != "service_tier" else None)
    )


def _tail_line(path, limit=4000):
    if not path:
        return None
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            handle.seek(max(0, size - limit))
            text = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1][:500]


def _provider_failure_message(error, run_info, error_code):
    base = str(error) if error else "Run failed."
    if error_code != "provider_failed":
        return base
    detail = _tail_line(run_info.get("stderr_path")) or _tail_line(run_info.get("stdout_path"))
    return f"{base}: {detail}" if detail else base


def run_error_arguments(error):
    """The argument names a `CdxArgumentError` blames, as data.

    Always a list so the error object keeps one shape: an empty list means the
    failure is not about specific arguments, never that the caller should go
    parse the message to find out.
    """
    return list(getattr(error, "arguments", ()) or [])


def run_error_allowed_values(error):
    allowed = getattr(error, "allowed", None)
    return list(allowed) if allowed else None


def run_effective_permission(parsed, session):
    launch = (session.get("launch") or {}) if session else {}
    return parsed.get("permission") or launch.get("permission")


def run_warnings(parsed, session, selection_row=None):
    """Known degradations that a zero exit code would otherwise hide.

    Emitted on success as much as on failure: the whole point is that the run
    looks fine and quietly did less than it was asked to.
    """
    warnings = []
    if selection_row is not None and selection_row.get("available_pct") is None:
        # Auto-selection ranked this session without ever having seen its
        # status. That is not "low availability" — it is no information, and on
        # a freshly imported or long-idle set of sessions it is the normal case.
        warnings.append({
            "code": "session_selected_without_status",
            "message": (
                f"Session {selection_row.get('session_name')!r} was auto-selected without any "
                "recorded availability; the choice was made on missing status data. "
                "Pass --refresh to fetch status before selecting."
            ),
            "session": selection_row.get("session_name"),
        })
    provider = session.get("provider") if session else parsed.get("provider")
    permission = run_effective_permission(parsed, session)
    if not parsed.get("network_access") and headless_permission_disables_network(provider, permission):
        described = repr(permission) if permission else "its default (none set)"
        warnings.append({
            "code": "network_disabled_by_permission",
            "message": (
                f"{provider} runs at permission {described} inside a sandbox with no network "
                "access, so tools needing the network (DNS, HTTPS) fail inside this run even "
                "though it exits successfully. Use --permission full if the run needs network."
            ),
            "provider": provider,
            "permission": permission,
        })
    return warnings


def run_launch_payload(api_schema_version, parsed, session, artifacts, cwd=None,
                       pid=None, launch_log_path=None, selection_row=None, conversation_id=None):
    """Payload for a detached launch: identity and artifact paths, no outcome.

    Deliberately shaped like `run_result_payload` minus the fields only a
    finished run can fill (`exit_code`, `duration_seconds`, `usage`), so a
    caller reads `run_id` from the same place either way.
    """
    return {
        "schema_version": api_schema_version,
        "ok": True,
        "action": "run",
        "launcher": "cdx",
        "parent_run_id": parsed.get("continue_run"),
        "conversation_id": conversation_id or run_conversation_id(session),
        "detached": True,
        "session": session.get("name") if session else None,
        "provider": session.get("provider") if session else parsed.get("provider"),
        "model": parsed.get("model") or ((session.get("launch") or {}).get("model") if session else None),
        "reasoning_effort": run_payload_reasoning_effort(parsed, session),
        "power": parsed.get("power") or ((session.get("launch") or {}).get("power") if session else None),
        "cwd": os.path.abspath(cwd or parsed.get("cwd") or os.getcwd()),
        "run_id": artifacts.get("run_id"),
        "pid": pid,
        "transcript_path": artifacts.get("transcript_path"),
        "stdout_path": artifacts.get("stdout_path"),
        "stderr_path": artifacts.get("stderr_path"),
        "launch_log_path": launch_log_path,
        "warnings": run_warnings(parsed, session, selection_row),
        "error": None,
    }


def run_result_payload(api_schema_version, ok, parsed, session, run_info=None,
                       error=None, error_source=None, error_code=None, selection_row=None):
    run_info = run_info or {}
    usage, usage_model = run_info.get("usage"), run_info.get("usage_model")
    if not isinstance(usage, dict):
        usage, usage_model = extract_run_observation(
            session.get("provider"), run_info.get("stdout_path"), session.get("authHome"),
        ) if session else (empty_usage(), None)
    message = None if ok else (
        _provider_failure_message(error, run_info, error_code)
        if error_source == "provider"
        else (str(error) if error else "Run failed.")
    )
    warnings = run_warnings(parsed, session, selection_row)
    if run_info.get("permission_denials"):
        warnings.append({
            "code": "permission_denials",
            "message": (
                "The provider reported denied tool calls. A denied tool may have been "
                "replaced successfully; check the denials and transcript for impact."
            ),
            "provider": session.get("provider") if session else parsed.get("provider"),
            "permission_denials": run_info["permission_denials"],
        })
    return {
        "schema_version": api_schema_version,
        "ok": bool(ok),
        "action": "run",
        "launcher": "cdx",
        "parent_run_id": parsed.get("continue_run"),
        "conversation_id": run_conversation_id(session, run_info),
        "session": session.get("name") if session else None,
        "provider": session.get("provider") if session else parsed.get("provider"),
        "model": run_info.get("effective_model", parsed.get("model") or ((session.get("launch") or {}).get("model") if session else None)),
        "recovery_events": run_info.get("recovery_events", []),
        "reasoning_effort": run_payload_reasoning_effort(parsed, session),
        "power": parsed.get("power") or ((session.get("launch") or {}).get("power") if session else None),
        "cwd": os.path.abspath(parsed.get("cwd") or os.getcwd()),
        "run_id": run_info.get("run_id"),
        "exit_code": run_info.get("returncode"),
        "duration_seconds": (run_info.get("duration_ms") / 1000.0) if run_info.get("duration_ms") is not None else None,
        "transcript_path": run_info.get("transcript_path"),
        "stdout_path": run_info.get("stdout_path"),
        "stderr_path": run_info.get("stderr_path"),
        "usage": usage,
        "usage_model": usage_model,
        "warnings": warnings,
        "error": None if ok else {
            "source": error_source or "cdx",
            "code": error_code or "cdx_error",
            "message": message,
            "arguments": run_error_arguments(error),
            "allowed_values": run_error_allowed_values(error),
            "provider_code": run_info.get("returncode") if error_source == "provider" else None,
        },
    }
