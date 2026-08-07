"""Run domain commands: run, runs, run-status, run-report, run-tail, select, schema.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import os
import subprocess
import sys

from ..cli_args import (
    RUN_REPORT_USAGE,
    RUN_STATUS_USAGE,
    RUNS_USAGE,
    _parse_run_args,
    _parse_run_id_json_args,
    _parse_run_tail_args,
    _parse_runs_args,
    _parse_schema_args,
    _parse_select_args,
    cdx_schema,
)
from ..cli_helpers import API_SCHEMA_VERSION, _json_failure, _json_success, _write_json
from ..errors import CdxError
from ..provider_runtime import _ensure_session_authentication, _headless_artifact_paths, _run_headless_provider_command
from ..run_command import read_run_prompt, run_cdx_error_code, run_launch_payload, run_result_payload
from ..run_registry import RunRegistry, build_code_review_report
from ..run_usage import extract_run_usage
from ..session_ranking import FACTOR_DESCRIPTIONS, rank_sessions, selection_policy
from ..status_view import _now_timestamp, _priority_reset_timestamp


def handle_select(rest, ctx):
    parsed = _parse_select_args(rest)
    selected = _select_headless_session(
        ctx,
        parsed["provider"],
        min_reasoning_effort=parsed["min_reasoning_effort"],
        require_ready=parsed["require_ready"],
        force_refresh=parsed["refresh"],
    )
    # Derived from the ranking rather than written by hand: the previous
    # literal omitted the reasoning-effort tie-break and described a candidate
    # filter as a sort stage, and nothing failed when the sort key moved on
    # without it.
    policy = selection_policy()
    if not selected:
        message = "No suitable session found."
        _write_json(ctx, _json_failure(
            "select",
            "no_suitable_session",
            message,
            provider=parsed["provider"],
            min_reasoning_effort=parsed["min_reasoning_effort"],
            require_ready=parsed["require_ready"],
            selection_policy=policy,
        ))
        return 1
    session = selected["session"]
    row = selected.get("row") or {}
    _write_json(ctx, _json_success(
        "select",
        f"Selected session {session['name']}",
        session=session["name"],
        provider=session["provider"],
        reason=_selection_reason(selected.get("decision")),
        deciding_factor=selected.get("decision"),
        selection_policy=policy,
        min_reasoning_effort=parsed["min_reasoning_effort"],
        reasoning_effort=row.get("reasoning_effort"),
        priority=row.get("priority"),
        available_pct=row.get("available_pct"),
        auth_status=row.get("auth_status"),
    ))
    return 0

def _selection_reason(decision):
    """Why this session won, for this call.

    Names the factor that actually separated it from the runner-up instead of
    the factor that usually does: the old fixed sentence claimed availability
    decided even when priority or the alphabetical fallback did.
    """
    if decision is None:
        return "only suitable session"
    return f"decided on {decision}: {FACTOR_DESCRIPTIONS[decision]}"

def _run_registry(ctx):
    return RunRegistry(ctx["service"]["base_dir"])

DETACHED_RUN_ID_ENV = "CDX_RUN_ID"

RUN_TAIL_READ_BYTES = 1 << 20

def _tail_file_lines(path, lines):
    """Last `lines` lines of a run's output, safe to call while it is still being written.

    Reads a bounded tail of the file in binary and decodes with replacement, so
    provider output containing undecodable bytes returns those lines instead of
    raising. A final line that is still mid-write is returned as-is: the caller
    asked what the run is doing right now, not for a complete record.
    """
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        truncated = size > RUN_TAIL_READ_BYTES
        handle.seek(max(0, size - RUN_TAIL_READ_BYTES))
        text = handle.read().decode("utf-8", errors="replace")
    found = text.splitlines()
    if truncated and found:
        # The window opened mid-line, so the first entry is a fragment. Codex
        # emits very long single-line JSON events, so this is reachable, and
        # handing a caller half a line as if it were whole is worse than one
        # line short.
        found = found[1:]
    return found[-lines:]

def _cdx_self_command():
    """argv prefix that re-runs this same cdx as a child process.

    `--detach` re-invokes cdx rather than forking: the child then walks the
    ordinary blocking run path, so registry bookkeeping, usage extraction,
    history, and the code-review report all happen exactly once, in code that
    is already tested, without a second implementation that only detached runs
    exercise. `os.fork()` would avoid the re-exec but is not available on
    Windows, which this CLI supports.

    Always goes through `sys.executable -m`, never `sys.argv[0]`: the console
    script has no reliable executable bit on Windows (`os.access(X_OK)` is true
    for any existing file there) and a shebang script handed to CreateProcess
    does not start at all.
    """
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [sys.executable, "-m", f"{__package__}.cli"], package_root

def _detached_spawn_options():
    """Platform flags that keep the child alive after this process exits.

    `start_new_session` is silently ignored on Windows, where a child stays
    attached to the console and dies with the launcher unless it is explicitly
    detached and given its own process group.
    """
    if sys.platform == "win32":
        detached_process = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": detached_process | new_group}
    return {"start_new_session": True}

def _detached_child_argv(parsed, prompt_path, session_name, cwd):
    """Child argv for a detached run.

    Always names the session the parent already resolved, never `--provider`:
    the parent may have auto-selected an account, and letting the child select
    again could land it on a different session than the one the launch payload
    just reported to the caller.
    """
    # The resolved absolute cwd, not the raw user string: the child is started
    # from the package root, so a relative "--cwd ." would resolve there.
    argv = ["run", session_name, "--cwd", cwd, "--prompt-file", prompt_path]
    for flag, key in (
        ("--model", "model"),
        ("--kind", "kind"),
        ("--permission", "permission"),
    ):
        value = parsed.get(key)
        if value:
            argv += [flag, str(value)]
    # reasoning_effort and power are normalized to the same value upstream;
    # passing one back is enough and avoids re-tripping the must-match check.
    if parsed.get("reasoning_effort"):
        argv += ["--reasoning-effort", str(parsed["reasoning_effort"])]
    if parsed.get("timeout_seconds"):
        argv += ["--timeout-seconds", str(parsed["timeout_seconds"])]
    argv.append("--json")
    return argv

DETACHED_PROMPT_SUFFIX = ".prompt.txt"

def _consume_detached_prompt_file(parsed, detached_run_id):
    """Delete the prompt file a detached launch staged for this child.

    The prompt is arbitrary, often sensitive text, and the rest of the codebase
    keeps it out of anything persisted (`REDACTED_PROMPT_ARG`, `sensitive_args`).
    Leaving the staged copy behind would put a permanent cleartext prompt in the
    session's log directory for every detached run. Only the child that was
    handed a run id removes it, and only a file this code wrote.
    """
    prompt_file = parsed.get("prompt_file")
    if not detached_run_id or not prompt_file or not prompt_file.endswith(DETACHED_PROMPT_SUFFIX):
        return
    try:
        os.remove(prompt_file)
    except OSError:
        pass

def _spawn_detached_run(parsed, prompt, artifacts, ctx, session_name, cwd):
    """Stage the prompt, then launch the child detached and return immediately.

    The prompt is written beside the run's other artifacts rather than to a
    temporary file so that nothing has to survive this process in order to
    clean it up, and so the child cannot lose its input if the launcher exits
    first.
    """
    # transcript_path is "<prefix>.log"; the other artifacts share that prefix.
    prefix = os.path.splitext(artifacts["transcript_path"])[0]
    prompt_path = f"{prefix}{DETACHED_PROMPT_SUFFIX}"
    launch_log_path = f"{prefix}.launch.log"
    with open(prompt_path, "w", encoding="utf-8") as handle:
        handle.write(prompt)

    command, package_root = _cdx_self_command()
    env = {**os.environ, DETACHED_RUN_ID_ENV: artifacts["run_id"]}
    if package_root:
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = f"{package_root}{os.pathsep}{existing}" if existing else package_root

    spawn = ctx.get("spawn_detached") or subprocess.Popen
    try:
        with open(launch_log_path, "w", encoding="utf-8", errors="replace") as log_file:
            child = spawn(
                command + _detached_child_argv(parsed, prompt_path, session_name, cwd),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                # Detach so the run outlives the launcher, including when cdx
                # was invoked over a non-interactive SSH command that closes as
                # soon as it returns.
                cwd=package_root or None,
                env=env,
                **_detached_spawn_options(),
            )
    except OSError as error:
        # Surface as a CdxError so handle_run's own handler marks the already
        # registered run failed, instead of letting a raw OSError escape as an
        # unhandled traceback on a --json call.
        raise CdxError(f"Failed to start detached cdx run: {error}", 126) from error
    return {"pid": getattr(child, "pid", None), "launch_log_path": launch_log_path}

def handle_schema(rest, ctx):
    _parse_schema_args(rest)
    _write_json(ctx, _json_success("schema", "Schema loaded.", **cdx_schema()))
    return 0

def handle_runs(rest, ctx):
    parsed = _parse_runs_args(rest)
    if not parsed["json"]:
        raise CdxError(RUNS_USAGE)
    since = parsed.get("since")
    runs = _run_registry(ctx).list(limit=parsed["limit"], since=since)
    warnings = []
    if since is not None and parsed.get("limit_given"):
        warnings.append({
            "code": "limit_ignored_with_since",
            "message": "--since returns every run completed after the cursor; --limit was ignored.",
        })
    _write_json(ctx, _json_success(
        "runs",
        "Runs loaded.",
        warnings=warnings,
        runs=runs,
        since=since.isoformat() if since is not None else None,
    ))
    return 0

def handle_run_tail(rest, ctx):
    parsed = _parse_run_tail_args(rest)
    run = _run_registry(ctx).get(parsed["run_id"])
    if not run:
        _write_json(ctx, _json_failure("run-tail", "run_not_found", f"Unknown run: {parsed['run_id']}"))
        return 1
    stdout_path = (run.get("artifacts") or {}).get("stdout_path")
    if not stdout_path:
        _write_json(ctx, _json_failure(
            "run-tail",
            "run_output_unavailable",
            f"No stdout_path recorded for run: {parsed['run_id']}",
            run_id=parsed["run_id"],
            status=run.get("status"),
        ))
        return 1
    try:
        lines = _tail_file_lines(stdout_path, parsed["lines"])
    except FileNotFoundError:
        if run.get("status") != "running":
            _write_json(ctx, _json_failure(
                "run-tail",
                "run_output_unreadable",
                f"Missing output file for a finished run: {stdout_path}",
                run_id=parsed["run_id"],
                stdout_path=stdout_path,
            ))
            return 1
        # A run registered a moment ago has not written its first byte yet.
        # That is "no output so far", not a failure — the advertised flow is
        # launch detached, then tail immediately, and a polling caller must not
        # read that window as fatal.
        lines = []
    except OSError as error:
        _write_json(ctx, _json_failure(
            "run-tail",
            "run_output_unreadable",
            f"Failed to read {stdout_path}: {error}",
            run_id=parsed["run_id"],
            stdout_path=stdout_path,
        ))
        return 1
    _write_json(ctx, _json_success(
        "run-tail",
        "Run output loaded.",
        run_id=parsed["run_id"],
        status=run.get("status"),
        stdout_path=stdout_path,
        lines=lines,
    ))
    return 0

def handle_run_status(rest, ctx):
    parsed = _parse_run_id_json_args(rest, RUN_STATUS_USAGE)
    run = _run_registry(ctx).get(parsed["run_id"])
    if not run:
        _write_json(ctx, _json_failure("run-status", "run_not_found", f"Unknown run: {parsed['run_id']}"))
        return 1
    _write_json(ctx, _json_success("run-status", "Run loaded.", run=run))
    return 0

def handle_run_report(rest, ctx):
    parsed = _parse_run_id_json_args(rest, RUN_REPORT_USAGE)
    run = _run_registry(ctx).get(parsed["run_id"])
    if not run:
        _write_json(ctx, _json_failure("run-report", "run_not_found", f"Unknown run: {parsed['run_id']}"))
        return 1
    _write_json(ctx, _json_success("run-report", "Run report loaded.", report={
        "run": run,
        "final_payload": run.get("final_payload"),
        "task_report": run.get("task_report"),
        "artifacts": run.get("artifacts") or {},
        "usage": run.get("usage"),
        "error": run.get("error"),
    }))
    return 0

def handle_run(rest, ctx):
    registry = None
    run_id = None
    selection_row = None
    # pop, not get: the variable is consumed once. Left in the environment it is
    # inherited by the provider process, and any nested `cdx run` the agent
    # itself makes would claim this same run_id — deleting this run's registry
    # record and truncating its stdout/stderr/transcript files.
    detached_run_id = os.environ.pop(DETACHED_RUN_ID_ENV, None) or None
    try:
        parsed = _parse_run_args(rest)
        session = None
        if parsed["name"]:
            session = ctx["service"]["get_session"](parsed["name"])
            if not session:
                raise CdxError(f"Unknown session: {parsed['name']}")
            if session.get("enabled", True) is False:
                raise CdxError(f"Session is disabled: {parsed['name']}")
        else:
            selected = _select_headless_session(
                ctx,
                parsed["provider"],
                min_reasoning_effort=parsed["reasoning_effort"],
                require_ready=True,
                # Cached by default: refreshing would make every auto-selected
                # run pay for a provider probe. `--refresh` is there for callers
                # that would rather pay than choose on stale data.
                force_refresh=parsed.get("refresh", False),
            )
            if not selected:
                _write_json(ctx, _json_failure(
                    "run",
                    "no_suitable_session",
                    "No suitable session found.",
                    launcher="cdx",
                    provider=parsed["provider"],
                ))
                return 1
            session = selected["session"]
            selection_row = selected.get("row") or {}

        cwd = os.path.abspath(parsed["cwd"])
        if not os.path.isdir(cwd):
            raise CdxError(f"Invalid cwd: {parsed['cwd']}")
        prompt = read_run_prompt(parsed, stdin=ctx.get("prompt_stdin"))
        _consume_detached_prompt_file(parsed, detached_run_id)
        launch_updates = {}
        if parsed.get("model"):
            launch_updates["model"] = parsed["model"]
        if parsed.get("permission"):
            launch_updates["permission"] = parsed["permission"]
        if parsed.get("reasoning_effort"):
            launch_updates["reasoning_effort"] = parsed["reasoning_effort"]
            launch_updates["power"] = parsed["reasoning_effort"]
        run_session = {
            **session,
            "launch": {
                **(session.get("launch") or {}),
                **launch_updates,
            },
        }
        _ensure_session_authentication(
            run_session,
            ctx["service"],
            spawn=ctx.get("spawn"),
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
            stdin_is_tty=False,
            behavior="launch",
            signal_emitter=ctx.get("signal_emitter"),
            trust_local_credentials=False,
        )
        registry = _run_registry(ctx)
        # A detached child is handed its parent's run_id so both agree on the
        # identity the launch payload already reported to the caller.
        # pop, not get: the variable is consumed once. Left in the environment
        # it is inherited by the provider process, and any nested `cdx run` the
        # agent itself makes would claim this same run_id — deleting this run's
        # registry record and truncating its stdout/stderr/transcript files.
        artifacts = _headless_artifact_paths(run_session, run_id=detached_run_id)
        run_id = artifacts["run_id"]
        registry.start(
            run_id,
            kind=parsed.get("kind"),
            session=run_session.get("name"),
            provider=run_session.get("provider"),
            model=parsed.get("model") or ((run_session.get("launch") or {}).get("model")),
            cwd=cwd,
            artifacts={
                "transcript_path": artifacts.get("transcript_path"),
                "stdout_path": artifacts.get("stdout_path"),
                "stderr_path": artifacts.get("stderr_path"),
            },
        )
        if parsed.get("detach"):
            launch = _spawn_detached_run(parsed, prompt, artifacts, ctx, run_session["name"], cwd)
            # Hand the record the child's pid: this process is about to exit,
            # and a run pointing at a dead pid gets swept up as stale.
            if launch.get("pid"):
                registry.set_pid(run_id, launch["pid"])
            _write_json(ctx, run_launch_payload(
                API_SCHEMA_VERSION,
                parsed,
                run_session,
                artifacts,
                cwd=cwd,
                pid=launch.get("pid"),
                launch_log_path=launch.get("launch_log_path"),
                selection_row=selection_row,
            ))
            return 0

        run_info = _run_headless_provider_command(
            run_session,
            cwd=cwd,
            env_override=ctx.get("env"),
            initial_prompt=prompt,
            timeout_seconds=parsed.get("timeout_seconds"),
            spawn=ctx.get("spawn_headless") or ctx.get("spawn"),
            run_id=run_id,
        )
        usage = extract_run_usage(run_session.get("provider"), run_info.get("stdout_path"))
        run_info = {**run_info, "usage": usage}
        ok = run_info.get("returncode") == 0
        if ok:
            final_payload = run_result_payload(
                API_SCHEMA_VERSION, True, parsed, run_session, run_info=run_info,
                selection_row=selection_row,
            )
            task_report = build_code_review_report(run_id, final_payload) if parsed.get("kind") == "code-review" else None
            registry.finish(
                run_id,
                status="succeeded",
                final_payload=final_payload,
                run_info=run_info,
                task_report=task_report,
            )
            ctx["service"]["record_launch_history"](session["name"], {
                "status": "success",
                "cwd": cwd,
                "exit_code": 0,
                **run_info,
            })
            _write_json(ctx, final_payload)
            return 0
        message = "Provider process timed out." if run_info.get("timed_out") else "Provider process exited with a non-zero status."
        error = CdxError(message, run_info.get("returncode") or 1)
        final_payload = run_result_payload(
            API_SCHEMA_VERSION,
            False,
            parsed,
            run_session,
            run_info=run_info,
            error=error,
            error_source="provider",
            error_code="provider_timeout" if run_info.get("timed_out") else "provider_failed",
            selection_row=selection_row,
        )
        registry.finish(
            run_id,
            status="timed_out" if run_info.get("timed_out") else "failed",
            final_payload=final_payload,
            run_info=run_info,
            error=final_payload.get("error"),
            task_report=build_code_review_report(run_id, final_payload) if parsed.get("kind") == "code-review" else None,
        )
        ctx["service"]["record_launch_history"](session["name"], {
            "status": "failed",
            "cwd": cwd,
            "error": str(error),
            "exit_code": error.exit_code,
            **run_info,
        })
        _write_json(ctx, final_payload)
        return error.exit_code or 1
    except CdxError as error:
        run_info = getattr(error, "run_info", None)
        final_payload = run_result_payload(
            API_SCHEMA_VERSION,
            False,
            locals().get("parsed", {}) or {},
            locals().get("session"),
            run_info=run_info,
            error=error,
            error_source="cdx",
            error_code=run_cdx_error_code(error),
            selection_row=selection_row,
        )
        if registry and run_id:
            registry.finish(
                run_id,
                status="failed",
                final_payload=final_payload,
                run_info=run_info,
                error=final_payload.get("error"),
            )
        _write_json(ctx, final_payload)
        return error.exit_code

def _select_headless_session(ctx, provider, min_reasoning_effort=None, require_ready=False, force_refresh=False):
    """The best session for a headless run, using the one shared ranking.

    Returns the winning session with its status row and why it won, or None if
    no candidate survived the filters.
    """
    sessions_by_name = {
        session["name"]: session for session in ctx["service"]["list_sessions"]()
    }
    rows = ctx["service"]["get_status_rows"](force_refresh=force_refresh)
    ordered, decision = rank_sessions(
        rows,
        _now_timestamp(),
        _priority_reset_timestamp,
        provider=provider,
        require_ready=require_ready,
        min_reasoning_effort=min_reasoning_effort,
    )
    for row in ordered:
        session = sessions_by_name.get(row.get("session_name"))
        if session:
            return {"session": session, "row": row, "decision": decision}
    return None
