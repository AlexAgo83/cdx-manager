"""Run domain commands: run, runs, run-status, run-report, run-tail, select, schema.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import time

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
from ..config import split_extra_args
from ..errors import CdxError
from ..interactive_usage import MATCH_CONVERSATION_ID, MEASURED_KEYS, extract_interactive_usage, usage_delta
from ..provider_background import (
    BACKGROUND_PATH_CDX,
    BACKGROUND_PATH_PROVIDER,
    agent_terminal_status,
    find_agent,
    find_session_transcript,
    list_background_agents,
    parse_backgrounded_id,
    read_transcript_outcome,
    stop_background_agent,
    supports_native_background,
    turn_is_complete,
)
from ..provider_runtime import (
    _build_launch_spec,
    _ensure_session_authentication,
    _headless_artifact_paths,
    _launch_power,
    _restore_signal_handlers,
    _route_termination_to_interrupt,
    _run_headless_provider_command,
    with_requested_conversation,
)
from ..run_command import read_run_prompt, run_cdx_error_code, run_launch_payload, run_result_payload
from ..run_failover import (
    CAPACITY_RETRY_DELAYS,
    MAX_FAILOVER_TRANSITIONS,
    capacity_models,
    failover_reason,
    looks_model_at_capacity,
)
from ..run_registry import RunRegistry, build_code_review_report, final_message
from ..run_usage import empty_usage, estimate_cost, extract_run_conversation_id, extract_run_observation, token_prices
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

    Named from the top-level package, not this module's own package: `cli` lives
    beside `commands`, so `{__package__}.cli` resolves to a module that does not
    exist. The import root is the parent of every package component, which for
    src/commands/runs.py is the repository root rather than src/.
    """
    package = (__package__ or "src.commands").split(".")[0]
    module = f"{package}.cli"
    package_root = os.path.abspath(__file__)
    for _ in range((__package__ or "src.commands").count(".") + 2):
        package_root = os.path.dirname(package_root)
    if importlib.util.find_spec(module) is None:
        # A wrong module name reports a launched run that never runs, so fail
        # here where the caller still gets the error.
        raise CdxError(f"Cannot launch a detached run: the cdx CLI module {module} was not found.")
    return [sys.executable, "-m", module], package_root

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
        ("--budget", "budget"),
        ("--continue-run", "continue_run"),
        ("--model", "model"),
        ("--kind", "kind"),
        ("--permission", "permission"),
        ("--label", "label"),
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
    # The child is the supervisor: it watches the run like any blocking one, so
    # it applies the failover rule and records each move in the registry.
    for key in ("network_access", "isolate_workspace", "failover"):
        if parsed.get(key):
            argv.append("--" + key.replace("_", "-"))
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
        raise CdxError(f"Failed to start detached cdx run: {error}", 126, code="provider_start_failed") from error
    return {
        "pid": getattr(child, "pid", None),
        "launch_log_path": launch_log_path,
        "background_path": BACKGROUND_PATH_CDX,
    }


def _spawn_provider_background_run(run_session, prompt, artifacts, ctx, cwd):
    """Start the run as the provider's own background agent.

    Returns the same shape as the in-house launcher so the caller does not
    branch on which path ran, plus the provider handle needed to observe it
    later. Returns None when the provider declines to start one, which sends
    the caller back to the in-house path rather than failing the run.
    """
    # Derived from the interactive spec, not the headless one. `--bg` starts a
    # session; it does not pass `--print`, and the headless spec is built around
    # flags the provider accepts only alongside `--print` - `--output-format`,
    # `--max-budget-usd`, `--fallback-model`. Reusing it and stripping `--print`
    # would hand the CLI print-only flags without `--print` and have the launch
    # rejected.
    spec = _build_launch_spec(
        run_session, cwd=cwd, env_override=ctx.get("env"),
        initial_prompt=prompt, capture_transcript=False,
    )
    argv = [spec["command"], "--bg"] + list(spec["args"])
    env = (spec.get("options") or {}).get("env")
    spawn = ctx.get("spawn_detached") or subprocess.Popen
    prefix = os.path.splitext(artifacts["transcript_path"])[0]
    launch_log_path = f"{prefix}.launch.log"
    try:
        with open(launch_log_path, "w", encoding="utf-8", errors="replace") as log_file:
            child = spawn(
                argv,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=cwd,
                env=env,
                **_detached_spawn_options(),
            )
        # --bg returns immediately, so this waits for the launcher itself, not
        # for the task: the id line is printed before it exits.
        if hasattr(child, "wait"):
            child.wait()
    except OSError:
        return None

    with open(launch_log_path, encoding="utf-8", errors="replace") as handle:
        identifier = parse_backgrounded_id(handle.read())
    if not identifier:
        # The agent may nonetheless be running. Falling back to the in-house
        # launcher here would run the same task twice, once untracked, on the
        # user's account - so this fails loudly instead.
        raise CdxError(
            "Started a provider background agent but it did not report an id; "
            "refusing to launch a second run for the same task.",
            126,
        )
    agent = find_agent(
        list_background_agents(env=env, cwd=cwd, spawn_sync=ctx.get("spawn_text")),
        identifier,
    ) or {}
    return {
        "pid": agent.get("pid"),
        "launch_log_path": launch_log_path,
        "background_path": BACKGROUND_PATH_PROVIDER,
        "provider_session_id": agent.get("sessionId") or identifier,
        "provider_agent_id": identifier,
    }

def handle_schema(rest, ctx):
    _parse_schema_args(rest)
    _write_json(ctx, _json_success("schema", "Schema loaded.", **cdx_schema()))
    return 0

def _reconcile_background_runs(ctx):
    """Close out delegated runs the provider has finished.

    A delegated run has no cdx child to report its own completion, so the
    registry would leave it `running` forever. This asks the provider once, on
    the read paths a caller actually uses, and closes what has finished -
    including the usage and final result read back from the session transcript,
    which is the only place a `--bg` run records them.

    Never raises: a provider that is slow, missing, or unparseable must not
    take down `cdx runs`.
    """
    registry = _run_registry(ctx)
    try:
        pending = [run for run in registry.list(limit=50)
                   if run.get("status") == "running"
                   and run.get("background_path") == BACKGROUND_PATH_PROVIDER]
    except Exception:
        return
    if not pending:
        return
    for run in pending:
        session = ctx["service"]["get_session"](run.get("session") or "")
        if not session:
            continue
        auth_home = session.get("authHome")
        env = {**os.environ, "HOME": auth_home} if auth_home else None
        try:
            outcome = read_transcript_outcome(
                find_session_transcript(auth_home, run.get("provider_session_id"))
            )
            # The transcript decides, not the agent state: a --bg session parks
            # after answering and never reports a terminal state on its own.
            if turn_is_complete(outcome):
                status = "succeeded"
            else:
                agents = list_background_agents(env=env, cwd=run.get("cwd"), spawn_sync=ctx.get("spawn_text"))
                status = agent_terminal_status(find_agent(agents, run.get("provider_session_id")))
            if not status:
                continue
            # `claude stop` accepts the short agent id only; the session id
            # names the transcript file and is rejected here.
            stop_background_agent(run.get("provider_agent_id"), env=env, spawn_sync=ctx.get("spawn_text"))
            registry.finish(
                run["run_id"],
                status=status,
                final_payload={
                    "usage": outcome["usage"],
                    "usage_model": outcome["usage_model"],
                    "result": outcome["result"],
                    "background_path": BACKGROUND_PATH_PROVIDER,
                },
            )
            ctx["service"]["record_launch_history"](session["name"], {
                "status": "success" if status == "succeeded" else "failed",
                "action": "run",
                "run_id": run["run_id"],
                "attempt": 1,
                "cwd": run.get("cwd"),
                "usage": outcome["usage"],
                "usage_model": outcome["usage_model"],
            })
        except Exception:
            continue


def handle_runs(rest, ctx):
    parsed = _parse_runs_args(rest)
    if not parsed["json"]:
        raise CdxError(RUNS_USAGE)
    since = parsed.get("since")
    _reconcile_background_runs(ctx)
    runs = _run_registry(ctx).list(limit=parsed["limit"], since=since, running=parsed.get("running", False))
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
    _reconcile_background_runs(ctx)
    run = _run_registry(ctx).get(parsed["run_id"])
    if not run:
        _write_json(ctx, _json_failure("run-status", "run_not_found", f"Unknown run: {parsed['run_id']}"))
        return 1
    _write_json(ctx, _json_success("run-status", "Run loaded.", run=run))
    return 0

def handle_run_report(rest, ctx):
    parsed = _parse_run_id_json_args(rest, RUN_REPORT_USAGE)
    _reconcile_background_runs(ctx)
    run = _run_registry(ctx).get(parsed["run_id"])
    if not run:
        _write_json(ctx, _json_failure("run-report", "run_not_found", f"Unknown run: {parsed['run_id']}"))
        return 1
    _write_json(ctx, _json_success("run-report", "Run report loaded.", report={
        "run": run,
        "final_payload": run.get("final_payload"),
        "final_message": final_message(run),
        "task_report": run.get("task_report"),
        "artifacts": run.get("artifacts") or {},
        "usage": run.get("usage"),
        "error": run.get("error"),
    }))
    return 0

def _env_max_runs(ctx):
    """CDX_MAX_RUNS as the default --max-parallel; unset, invalid or <= 0 means no limit."""
    value = {**os.environ, **(ctx.get("env") or {})}.get("CDX_MAX_RUNS")
    try:
        limit = int(value) if value else 0
    except ValueError:
        return None
    # 0 or negative reads as "no limit", like unset, rather than a cap of 1.
    return limit if limit > 0 else None


def _observe_headless_usage(session, run_info, baseline=None):
    usage, model = extract_run_observation(session.get("provider"), run_info.get("stdout_path"), session.get("authHome"))
    observation = {"usage": usage, "usage_model": model}
    if baseline is not None:
        cumulative, path, match, transcript_model = extract_interactive_usage(
            session["provider"], session.get("authHome"), conversation_id=(session.get("conversation") or {}).get("id"))
        before, before_path, _before_match, _before_model = baseline
        comparable = (cumulative and before and path == before_path
                      and all((cumulative.get(key) is None) == (before.get(key) is None) for key in MEASURED_KEYS))
        # A newly reported split includes unknown pre-launch usage; losing a
        # split also prevents a comparable measurement across the boundary.
        delta = usage_delta(cumulative, before, provider=session.get("provider")) if comparable else None
        # Exec resume can emit conversation totals. Only exact launch boundaries
        # establish this run's share; stdout cannot replace a missing boundary.
        observation.update(usage=delta if delta is not None else empty_usage(), usage_cumulative=cumulative,
                           usage_attribution="launch_boundary" if delta is not None else "continuation_usage_unavailable",
                           provider_transcript_path=path, provider_transcript_match=match,
                           usage_model=model or transcript_model)
    return observation


def _budget_observation(session, paths, baseline):
    observation = _observe_headless_usage(session, paths, baseline if session["provider"] == "codex" else None)
    identifier = (extract_run_conversation_id(session["provider"], paths.get("stdout_path"))
                  or ((session.get("conversation") or {}).get("id")
                      if session["provider"] == "claude" or session.get("continue_run") else None))
    if not identifier:
        return observation
    usage, path, match, model = extract_interactive_usage(
        session["provider"], session.get("authHome"), conversation_id=identifier)
    if usage is None or match != MATCH_CONVERSATION_ID:
        return observation
    if baseline is not None:
        before, before_path, _match, _model = baseline
        comparable = (before and path == before_path
                      and all((usage.get(key) is None) == (before.get(key) is None) for key in MEASURED_KEYS))
        usage = usage_delta(usage, before, provider=session["provider"]) if comparable else None
    if usage is not None:
        return {**observation, "usage": usage, "usage_model": model, "provider_transcript_path": path,
                "provider_transcript_match": match}
    return observation


def _continue_run_session(parsed, ctx):
    """Resolve only the parent's profile and exact persisted conversation."""
    previous = _run_registry(ctx).get(parsed["continue_run"])
    if not previous:
        raise CdxError(f"Cannot continue unknown run: {parsed['continue_run']}. Start a normal run instead.",
                       code="continue_run_not_found")
    name, provider = previous.get("session"), previous.get("provider")
    if (parsed.get("name") and parsed["name"] != name) or (parsed.get("provider") and parsed["provider"] != provider):
        raise CdxError("Cannot continue a run from another profile or provider. Start a normal run instead.",
                       code="continue_run_mismatch")
    session = ctx["service"]["get_session"](name) if name else None
    if not session or session.get("provider") != provider:
        raise CdxError("The previous run's profile or provider is no longer available. Start a normal run instead.",
                       code="continue_run_mismatch")
    if provider not in ("claude", "codex") or previous.get("status") not in ("succeeded", "failed", "timed_out", "cancelled"):
        raise CdxError("Only a finished Claude or Codex run can be continued. Start a normal run instead.",
                       code="continue_run_unavailable")
    conversation = previous.get("conversation_id")
    resumed = with_requested_conversation(session, conversation)
    if not resumed:
        raise CdxError("The previous run's provider session expired or its transcript is missing. Start a normal run instead.",
                       code="continue_run_unavailable")
    model = previous.get("usage_model") or previous.get("model")
    effort = previous.get("reasoning_effort")
    if not isinstance(model, str) or not model or model.startswith("<") or not effort or not previous.get("launch"):
        raise CdxError("The previous run's model and effort cannot be pinned. Start a normal run instead.",
                       code="continue_run_unavailable")
    if ((parsed.get("model") and parsed["model"] != model)
            or (parsed.get("reasoning_effort") and parsed["reasoning_effort"] != effort)):
        raise CdxError("--continue-run requires the previous run's model and reasoning effort.",
                       code="continue_run_settings_mismatch")
    if parsed.get("failover") or parsed.get("isolate_workspace"):
        raise CdxError("--continue-run cannot be combined with --failover or --isolate-workspace.",
                       code="continue_run_settings_mismatch")
    if provider == "claude":
        # Passthrough options are appended last and can override the pinned settings.
        pinned_options = {"--model", "--effort", "--fallback-model", "--resume", "--continue",
                          "--session-id", "--fork-session", "--resume-session-at", "--from-pr",
                          "--settings", "--agent", "--agents"}
        for arg in split_extra_args((session.get("launch") or {}).get("extra_args")) or []:
            if arg.split("=", 1)[0] in pinned_options or arg.startswith(("-r", "-c")):
                raise CdxError("--continue-run cannot use Claude extra_args that override model, effort, or conversation.",
                               code="continue_run_settings_mismatch")
    parsed.update(name=name, model=model, reasoning_effort=effort, power=effort)
    launch = {**(session.get("launch") or {}), "model": model, "reasoning_effort": effort, "power": effort}
    # A provider fallback would break the model pin even though cdx stayed on this profile.
    launch.pop("fallback_model", None)
    return {**resumed, "launch": launch, "continue_run": parsed["continue_run"]}


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
        budget_prices = token_prices()[0] if parsed.get("budget") is not None else None
        session = _continue_run_session(parsed, ctx) if parsed.get("continue_run") else None
        if session:
            if session.get("enabled", True) is False:
                raise CdxError(f"Session is disabled: {session['name']}", code="session_disabled")
        elif parsed["name"]:
            session = ctx["service"]["get_session"](parsed["name"])
            if not session:
                raise CdxError(f"Unknown session: {parsed['name']}")
            if session.get("enabled", True) is False:
                raise CdxError(f"Session is disabled: {parsed['name']}", code="session_disabled")
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
            raise CdxError(f"Invalid cwd: {parsed['cwd']}", code="invalid_cwd")
        prompt = read_run_prompt(parsed, stdin=ctx.get("prompt_stdin"))
        _consume_detached_prompt_file(parsed, detached_run_id)
        launch_updates = {key: parsed.get(key, False) for key in ("network_access", "isolate_workspace")}
        if parsed.get("model"):
            launch_updates["model"] = parsed["model"]
        if parsed.get("permission"):
            launch_updates["permission"] = parsed["permission"]
        if parsed.get("reasoning_effort"):
            launch_updates["reasoning_effort"] = parsed["reasoning_effort"]
            launch_updates["power"] = parsed["reasoning_effort"]
        # A detached child runs in the slot its parent already took.
        max_parallel = None if detached_run_id else (parsed.get("max_parallel") or _env_max_runs(ctx))
        if max_parallel:
            # Before anything changes the session: a refused run must not leave
            # Claude on a fresh conversation id that resume and rescue then
            # point at. Finished native background runs are closed out first,
            # since nothing else frees their slot.
            _reconcile_background_runs(ctx)
            _run_registry(ctx).check_capacity(max_parallel)
        # Claude needs its conversation id before the spec is built; Codex
        # records its own afterwards, from the rollout. Without this a headless
        # Claude run left the session with no identity and `cdx resume` fell
        # back to recency for Claude while working by id for Codex.
        if not parsed.get("continue_run"):
            session = ctx["service"]["begin_conversation"](session["name"])
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
            label=parsed.get("label"),
            max_parallel=max_parallel,
            parent_run_id=parsed.get("continue_run"),
            conversation_id=(run_session.get("conversation") or {}).get("id") if run_session["provider"] == "claude" or parsed.get("continue_run") else None,
            launch=run_session.get("launch"),
            reasoning_effort=_launch_power(run_session),
        )
        if parsed.get("detach"):
            # Delegate where the installed CLI can both start a background
            # agent and report on it; fall back to the in-house launcher
            # otherwise, and whenever the provider declines to start one.
            launch = None
            # A provider's own background agent has no cdx process watching it,
            # so nothing could fail it over; --failover keeps the in-house child.
            if not parsed.get("budget") and not parsed.get("continue_run") and not parsed.get("isolate_workspace") and not parsed.get("network_access") and not parsed.get("failover") and supports_native_background(
                run_session.get("provider"),
                env=ctx.get("env"),
                spawn_sync=ctx.get("spawn_text"),
            ):
                launch = _spawn_provider_background_run(run_session, prompt, artifacts, ctx, cwd)
            if launch is None:
                launch = _spawn_detached_run(parsed, prompt, artifacts, ctx, run_session["name"], cwd)
            registry.record_background(
                run_id,
                path=launch.get("background_path"),
                provider_session_id=launch.get("provider_session_id"),
                provider_agent_id=launch.get("provider_agent_id"),
            )
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
                conversation_id=launch.get("provider_session_id"),
                selection_row=selection_row,
            ))
            return 0

        attempted = [run_session["name"]]
        failover_error_code = None
        recovery_events = []
        attempt = 0
        spent_usd = 0.0
        models = capacity_models(run_session)
        model_index = 0
        capacity_retries = 0
        while True:
            attempt += 1
            baseline = extract_interactive_usage(
                run_session["provider"], run_session.get("authHome"),
                conversation_id=(run_session.get("conversation") or {}).get("id"),
            ) if parsed.get("continue_run") and (run_session["provider"] == "codex" or parsed.get("budget")) else None
            attempt_cost = None
            budget_observation = None

            def check_budget(paths, session=run_session, before=baseline, already_spent=spent_usd):
                nonlocal attempt_cost, budget_observation
                observation = _budget_observation(session, paths, before)
                cost = estimate_cost(observation["usage"], observation["usage_model"], budget_prices)
                if cost is not None:
                    if attempt_cost is None or cost >= attempt_cost:
                        attempt_cost = cost
                        budget_observation = observation
                return attempt_cost is not None and already_spent + attempt_cost >= parsed["budget"]

            run_info = _run_headless_provider_command(
                run_session,
                cwd=cwd,
                env_override=ctx.get("env"),
                initial_prompt=prompt,
                timeout_seconds=parsed.get("timeout_seconds"),
                spawn=ctx.get("spawn_headless") or ctx.get("spawn"),
                run_id=run_id,
                **({"budget_check": check_budget} if parsed.get("budget") is not None else {}),
            )
            observation = _observe_headless_usage(run_session, run_info, baseline if run_session["provider"] == "codex" else None)
            if run_info.get("budget_exceeded") and budget_observation is not None:
                observation = budget_observation
            run_info = {**run_info, **observation,
                        "parent_run_id": parsed.get("continue_run"),
                        "conversation_id": extract_run_conversation_id(run_session.get("provider"), run_info.get("stdout_path"))
                        or ((run_session.get("conversation") or {}).get("id") if run_session["provider"] == "claude" or parsed.get("continue_run") else None),
                        "launch": run_session.get("launch"),
                        "reasoning_effort": _launch_power(run_session),
                        "effective_model": (run_session.get("launch") or {}).get("model"),
                        "recovery_events": recovery_events}
            cost = estimate_cost(observation["usage"], observation["usage_model"], budget_prices)
            spent_usd += max(attempt_cost or 0.0, cost or 0.0)
            if parsed.get("budget") is not None and (run_info.get("budget_exceeded") or spent_usd >= parsed["budget"]):
                run_info.update(budget_exceeded=True, returncode=125, cost_usd=spent_usd)
            ctx["service"]["record_launch_history"](run_session["name"], {
                "status": "success" if run_info.get("returncode") == 0 else "failed",
                "action": "run",
                "run_id": run_id,
                "attempt": attempt,
                "cwd": cwd,
                "exit_code": run_info.get("returncode"),
                **run_info,
            })
            if run_info.get("budget_exceeded") or parsed.get("continue_run"):
                break
            if looks_model_at_capacity(run_session.get("provider"), run_info):
                event = {"reason": "model_at_capacity", "attempt": attempt,
                         "session": run_session["name"], "model": models[model_index]}
                if capacity_retries < len(CAPACITY_RETRY_DELAYS):
                    delay = CAPACITY_RETRY_DELAYS[capacity_retries]
                    capacity_retries += 1
                    event.update(action="retry", retry=capacity_retries, delay_seconds=delay)
                elif model_index + 1 < len(models):
                    model_index += 1
                    capacity_retries = 0
                    run_session["launch"]["model"] = models[model_index]
                    event.update(action="fallback_model", target_model=models[model_index])
                else:
                    successor = None if len(attempted) > MAX_FAILOVER_TRANSITIONS else _select_headless_session(
                        ctx, "codex", min_reasoning_effort=parsed["reasoning_effort"],
                        require_ready=True, exclude=attempted,
                    )
                    if not successor:
                        failover_error_code = "capacity_recovery_exhausted"
                        event.update(action="exhausted")
                    else:
                        selection_row = successor.get("row") or {}
                        next_session = successor["session"]
                        run_session = {**next_session, "launch": {**(next_session.get("launch") or {}), **launch_updates}}
                        # Each new profile starts with the requested model, or its own default.
                        models = capacity_models(run_session)
                        model_index = capacity_retries = 0
                        attempted.append(run_session["name"])
                        event.update(action="fallback_profile", target_session=run_session["name"], target_model=models[0])
                _record_capacity_recovery(ctx, registry, run_id, event, run_info, recovery_events)
                if failover_error_code:
                    break
                if event["action"] == "retry":
                    previous_handlers = _route_termination_to_interrupt()
                    try:
                        time.sleep(event["delay_seconds"])
                    except KeyboardInterrupt as interrupt:
                        error = CdxError("Codex capacity recovery was cancelled.", 130)
                        error.cancelled = True
                        error.history_recorded = True
                        error.run_info = {**run_info, "returncode": 130}
                        raise error from interrupt
                    finally:
                        _restore_signal_handlers(previous_handlers)
                elif event["action"] == "fallback_profile":
                    _ensure_session_authentication(
                        run_session, ctx["service"], spawn=ctx.get("spawn"), spawn_sync=ctx.get("spawn_sync"),
                        env_override=ctx.get("env"), stdin_is_tty=False, behavior="launch",
                        signal_emitter=ctx.get("signal_emitter"), trust_local_credentials=False,
                    )
                    registry.migrate(run_id, session=run_session["name"], provider="codex", reason="model_at_capacity")
                continue
            if run_info.get("returncode") == 0 or not parsed.get("failover"):
                break
            reason = failover_reason(
                run_session.get("provider"),
                run_info,
                _status_row_for(ctx, run_session["name"]),
            )
            if not reason:
                break
            if len(attempted) > MAX_FAILOVER_TRANSITIONS:
                # A systematic misclassification must not be able to walk one
                # task through every account the user owns.
                failover_error_code = "failover_limit_reached"
                break
            successor = _select_headless_session(
                ctx,
                parsed["provider"] or run_session.get("provider"),
                min_reasoning_effort=parsed["reasoning_effort"],
                require_ready=True,
                force_refresh=False,
                exclude=attempted,
            )
            if not successor:
                failover_error_code = "failover_exhausted"
                break
            selection_row = successor.get("row") or {}
            run_session = {
                **successor["session"],
                "launch": {**(successor["session"].get("launch") or {}), **launch_updates},
            }
            attempted.append(run_session["name"])
            models = capacity_models(run_session)
            model_index = capacity_retries = 0
            # A different account means different credentials; an unauthenticated
            # successor would fail for a reason unrelated to the task.
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
            registry.migrate(
                run_id,
                session=run_session["name"],
                provider=run_session.get("provider"),
                reason=reason,
            )
            # The successor is a different account with its own auth, so the
            # context the task built so far travels with it as the prompt.
            prompt = _failover_prompt(prompt, attempted)
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
            _write_json(ctx, final_payload)
            return 0
        if run_info.get("budget_exceeded"):
            failover_error_code = "budget_exceeded"
            message = "Run exceeded its estimated USD budget."
        elif failover_error_code == "capacity_recovery_exhausted":
            message = "Codex model capacity recovery exhausted its retry, model, or profile budget."
        elif failover_error_code == "failover_exhausted":
            message = f"Every eligible session was rate limited: {', '.join(attempted)}."
        elif failover_error_code == "failover_limit_reached":
            message = f"Failover stopped after {MAX_FAILOVER_TRANSITIONS} transitions: {', '.join(attempted)}."
        elif run_info.get("timed_out"):
            message = "Provider process timed out."
        else:
            message = "Provider process exited with a non-zero status."
        error = CdxError(message, run_info.get("returncode") or 1)
        final_payload = run_result_payload(
            API_SCHEMA_VERSION,
            False,
            parsed,
            run_session,
            run_info=run_info,
            error=error,
            error_source="cdx" if run_info.get("budget_exceeded") else "provider",
            # Running out of accounts is a different outcome from the task
            # failing, and a caller has to be able to branch on which happened.
            error_code=failover_error_code or (
                "provider_timeout" if run_info.get("timed_out") else "provider_failed"
            ),
            selection_row=selection_row,
        )
        registry.finish(
            run_id,
            status="timed_out" if run_info.get("timed_out") and not run_info.get("budget_exceeded") else "failed",
            final_payload=final_payload,
            run_info=run_info,
            error=final_payload.get("error"),
            task_report=build_code_review_report(run_id, final_payload) if parsed.get("kind") == "code-review" else None,
        )
        _write_json(ctx, final_payload)
        return error.exit_code or 1
    except CdxError as error:
        run_info = getattr(error, "run_info", None)
        cancelled = bool(getattr(error, "cancelled", False))
        if run_info is not None:
            run_info = {**run_info, "recovery_events": locals().get("recovery_events", [])}
        if run_info and run_id and not getattr(error, "history_recorded", False):
            observation = _observe_headless_usage(run_session, run_info, locals().get("baseline"))
            run_info = {**run_info, **observation,
                        "parent_run_id": parsed.get("continue_run"),
                        "conversation_id": extract_run_conversation_id(run_session.get("provider"), run_info.get("stdout_path"))
                        or ((run_session.get("conversation") or {}).get("id") if run_session["provider"] == "claude" or parsed.get("continue_run") else None),
                        "launch": run_session.get("launch"), "reasoning_effort": _launch_power(run_session)}
            ctx["service"]["record_launch_history"](run_session["name"], {
                "status": "failed",
                "action": "run",
                "run_id": run_id,
                "attempt": locals().get("attempt", 1),
                "cwd": cwd,
                "exit_code": error.exit_code,
                **run_info,
            })
        final_payload = run_result_payload(
            API_SCHEMA_VERSION,
            False,
            locals().get("parsed", {}) or {},
            locals().get("run_session", locals().get("session")),
            run_info=run_info,
            error=error,
            error_source="provider" if cancelled else "cdx",
            error_code="run_cancelled" if cancelled else run_cdx_error_code(error),
            selection_row=selection_row,
        )
        final_payload["recovery_events"] = locals().get("recovery_events", [])
        if registry and run_id:
            registry.finish(
                run_id,
                # A cancelled run is neither a task failure nor a timeout, and a
                # caller has to be able to tell the three apart.
                status="cancelled" if cancelled else "failed",
                final_payload=final_payload,
                run_info=run_info,
                error=final_payload.get("error"),
            )
        _write_json(ctx, final_payload)
        return error.exit_code

def _record_capacity_recovery(ctx, registry, run_id, event, run_info, events):
    # Subsequent attempts reuse the run's paths; retain the failed output first.
    artifacts = {}
    for key in ("stdout_path", "stderr_path", "transcript_path"):
        path = run_info.get(key)
        if path and os.path.isfile(path):
            archived = f"{path}.attempt-{event['attempt']}"
            shutil.copyfile(path, archived)
            artifacts[key] = archived
    event["artifacts"] = artifacts
    events.append(event)
    registry.record_recovery(run_id, event)
    details = ", ".join(f"{key}={value}" for key, value in event.items() if key != "artifacts")
    ctx["err"](f"cdx capacity recovery: {details}\n")


def _select_headless_session(
    ctx, provider, min_reasoning_effort=None, require_ready=False, force_refresh=False, exclude=None,
):
    """The best session for a headless run, using the one shared ranking.

    Returns the winning session with its status row and why it won, or None if
    no candidate survived the filters. `exclude` drops sessions a failover has
    already tried, which is the only selection input failover adds - the
    ranking itself is untouched.
    """
    excluded = set(exclude or ())
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
        name = row.get("session_name")
        if name in excluded:
            continue
        session = sessions_by_name.get(name)
        if session:
            return {"session": session, "row": row, "decision": decision}
    return None


def _failover_prompt(prompt, attempted):
    """The prompt the successor account receives.

    What travels is the task, plus the fact that earlier accounts ran out
    mid-way. What does NOT travel is the provider conversation: the successor
    is a different account with its own auth and its own history, so it starts
    fresh. Any work the previous attempt left on disk is still on disk, which
    is why the note tells the assistant to check before redoing it.
    """
    previous = ", ".join(attempted[:-1])
    return (
        "This task was already started on another account "
        f"({previous}) and stopped when that account hit its rate limit. "
        "Work already written to the working tree is still there; check the "
        "current state before redoing anything.\n\n"
        f"{prompt}"
    )


def _status_row_for(ctx, name):
    """The status to corroborate a rate-limited termination against.

    Forced refresh on purpose: this runs once per rate-limited termination. The
    Codex probe spawns app-server and can rotate the OAuth token, which is why
    the cache exists, so this must stay rare and must never be called in a loop.

    A refresh that comes back with no readable window falls back to the stored
    status rather than being taken as "not exhausted": a failed probe is an
    absence of evidence, and the account may well have a recorded 0% from the
    moment it stopped answering.
    """
    def _read(force_refresh):
        try:
            return ctx["service"]["get_status_row"](name, force_refresh=force_refresh)
        except CdxError:
            return None

    row = _read(True)
    if row and any(row.get(key) is not None for key in ("remaining_5h_pct", "remaining_week_pct")):
        return row
    return _read(False) or row
