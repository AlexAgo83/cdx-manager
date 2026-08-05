import os

from .errors import CdxError
from .run_usage import empty_usage, extract_run_usage


def read_run_prompt(parsed):
    if parsed.get("prompt") is not None:
        return parsed["prompt"]
    try:
        with open(parsed["prompt_file"], encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise CdxError(f"Unable to read prompt file: {parsed['prompt_file']}") from error


def run_cdx_error_code(error):
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


def run_result_payload(api_schema_version, ok, parsed, session, run_info=None,
                       error=None, error_source=None, error_code=None):
    run_info = run_info or {}
    usage = run_info.get("usage") if isinstance(run_info.get("usage"), dict) else (
        extract_run_usage(session.get("provider"), run_info.get("stdout_path"))
        if session else
        empty_usage()
    )
    message = None if ok else (
        _provider_failure_message(error, run_info, error_code)
        if error_source == "provider"
        else (str(error) if error else "Run failed.")
    )
    return {
        "schema_version": api_schema_version,
        "ok": bool(ok),
        "action": "run",
        "launcher": "cdx",
        "session": session.get("name") if session else None,
        "provider": session.get("provider") if session else parsed.get("provider"),
        "model": parsed.get("model") or ((session.get("launch") or {}).get("model") if session else None),
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
        "warnings": [],
        "error": None if ok else {
            "source": error_source or "cdx",
            "code": error_code or "cdx_error",
            "message": message,
            "provider_code": run_info.get("returncode") if error_source == "provider" else None,
        },
    }
