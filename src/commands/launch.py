"""Launch domain commands: launch, resume, can-resume, handoff.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import os
import shlex

from ..agent_notify import notifications_enabled, provision, supports_agent_alerts
from ..cli_args import CAN_RESUME_USAGE, HANDOFF_USAGE, RESUME_USAGE, _parse_json_flag
from ..cli_helpers import (
    API_SCHEMA_VERSION,
    _json_failure,
    _json_success,
    _resume_capability_for_session,
    _update_notice_warnings,
    _warn_if_session_already_running,
    _write_json,
    _write_update_notice,
)
from ..cli_render import _dim, _info, _success, _warn
from ..config import PROVIDER_CODEX
from ..errors import CdxError
from ..handoff import HandoffSourceError, launch_prompt, load_entry, prepare_entry, resolve_source
from ..interactive_usage import extract_interactive_usage, transcript_predates_run, usage_delta
from ..provider_runtime import (
    INTERRUPT_EXIT_CODES,
    _conversation_id,
    _ensure_session_authentication,
    _get_auth_home,
    _run_interactive_provider_command,
)
from ..run_usage import estimate_cost


def _parse_launch_args(args):
    """Return the per-launch directory and ordinary launch flags."""
    directory = None
    cleaned = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--dir":
            if directory is not None or index + 1 >= len(args):
                raise CdxError("Usage: cdx <name> [--dir PATH] [--resume] [--json]")
            directory = args[index + 1]
            index += 2
            continue
        if arg.startswith("--dir="):
            if directory is not None or not arg.split("=", 1)[1]:
                raise CdxError("Usage: cdx <name> [--dir PATH] [--resume] [--json]")
            directory = arg.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    return directory, cleaned


def _launch_directory(session, ctx, explicit, json_flag):
    cwd = os.path.realpath(explicit) if explicit else (ctx.get("cwd") or os.getcwd())
    if explicit and not os.path.isdir(cwd):
        raise CdxError(f"Invalid directory: {explicit or cwd}")
    if explicit or json_flag or not ctx["stdin_is_tty"] or cwd not in {os.path.realpath(os.path.expanduser("~")), os.path.realpath(os.path.sep)}:
        return cwd
    recent = []
    for entry in ctx["service"]["get_launch_history"](session["name"], limit=20):
        path = entry.get("cwd")
        if path and os.path.isdir(path) and path not in recent:
            recent.append(path)
    choices = recent + [cwd]
    if len(choices) == 1:
        return cwd
    ask = ctx["options"].get("input") or input
    other_index = len(choices) + 1
    while True:
        ctx["out"](
            "Choose launch directory:\n"
            + "".join(f"  {index + 1}. {path}\n" for index, path in enumerate(choices))
            + f"  {other_index}. Other (enter a path)\n"
        )
        try:
            answer = ask(f"Directory [1-{other_index}] (default {len(choices)}): ").strip()
        except KeyboardInterrupt:
            raise CdxError("Launch cancelled.", exit_code=130) from None
        if not answer:
            return cwd
        try:
            choice = int(answer)
        except ValueError:
            raise CdxError("Launch cancelled: choose a listed directory.") from None
        if choice == other_index:
            while True:
                try:
                    entered = ask("Directory path (blank to return): ").strip()
                except KeyboardInterrupt:
                    raise CdxError("Launch cancelled.", exit_code=130) from None
                if not entered:
                    break
                directory = os.path.realpath(entered)
                if os.path.isdir(directory):
                    return directory
                ctx["out"](f"Invalid directory: {entered}\n")
            continue
        try:
            return choices[choice - 1]
        except IndexError:
            raise CdxError("Launch cancelled: choose a listed directory.") from None


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
    directory, rest = _parse_launch_args(rest)
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError(RESUME_USAGE)
    return handle_launch(args[0], ctx, resume=True, force_json=json_flag, directory=directory)


def _notification_provisioning_enabled(session, ctx, json_flag):
    """Ask once before the first supported profile receives a hook."""
    enabled = notifications_enabled(session)
    if enabled or not supports_agent_alerts(session["provider"]):
        return enabled
    from ..tray_defaults import alerts_default, set_alerts_default

    base_dir = ctx["service"]["base_dir"]
    if alerts_default(base_dir):
        return True
    if not ctx["stdin_is_tty"] or json_flag:
        return False
    ask = ctx.get("options", {}).get("input") or input
    try:
        answer = ask("Allow CDX to install this provider's agent-alert hook? [y/N] ").strip().lower()
    except EOFError:
        return False
    if answer not in ("y", "yes"):
        return False
    set_alerts_default(base_dir, True)
    from ..tray_alerts import set_alerts
    set_alerts(base_dir, False)
    return True


def handle_launch(command, ctx, initial_prompt=None, resume=False, force_json=None, directory=None):
    json_flag = "--json" in ctx.get("raw_args", ctx["options"].get("raw_args", []))
    if force_json is not None:
        json_flag = force_json
    warnings = _update_notice_warnings(ctx)
    _warn_if_session_already_running(command, ctx)
    session = ctx["service"]["get_session"](command)
    if not session:
        raise CdxError(f"Unknown session: {command}")
    if session.get("enabled", True) is False:
        raise CdxError(f"Session is disabled: {command}")
    capability = _resume_capability_for_session(session, ctx) if resume else None
    if capability and not capability["resumable"]:
        raise CdxError(
            f"Provider {session['provider']} does not support native resume through cdx."
        )
    cwd = _launch_directory(session, ctx, directory, json_flag)
    session = ctx["service"]["launch_session"](command, resume=resume)
    capability = _resume_capability_for_session(session, ctx) if resume else None
    if not json_flag and not ctx["stdin_is_tty"]:
        ctx["out"](f"Using directory: {cwd}\n")
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
    alerts_allowed = _notification_provisioning_enabled(session, ctx, json_flag)
    installed = provision(
        _get_auth_home(session),
        session["provider"],
        alerts_allowed,
        ctx.get("env"),
        spawn_sync=ctx.get("spawn_sync"),
        base_dir=ctx["service"]["base_dir"],
    )
    if installed and not json_flag:
        notice = f"Notification hooks installed for {session['name']}"
        if session["provider"] == PROVIDER_CODEX:
            # Codex refuses to run a hook it has not been told to trust, so
            # silence here would leave the user with a feature that quietly does
            # nothing. Claude Code honours them straight away — verified against
            # a real turn — so it gets no instruction it does not need.
            notice += " — approve them once in Codex to enable"
        ctx["out"](f"{_info(notice, ctx['use_color'])}\n")
    runtime_run_id = None

    def runtime_lifecycle(event, info):
        nonlocal runtime_run_id
        if event == "started":
            runtime = ctx["service"]["start_session_runtime"](session["name"], {**info, "cwd": cwd})
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
            # A JSON run owns stdout: a terminal title sequence would land in
            # the middle of the document its caller has to parse.
            title_enabled=not json_flag,
        )
    except CdxError as error:
        run_info = getattr(error, "run_info", {}) or {}
        run_info = _attach_interactive_usage(
            session, run_info, ctx["service"]["get_launch_history"](session["name"], limit=50)
        )
        if not json_flag and error.exit_code in INTERRUPT_EXIT_CODES:
            ctx["out"](f"{_goodbye_line(session, run_info, ctx['use_color'])}\n")
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
    success_run_info = _attach_interactive_usage(
        session, run_info, ctx["service"]["get_launch_history"](session["name"], limit=50)
    )
    ctx["service"]["record_launch_history"](session["name"], {
        "status": "success",
        "action": "resume" if resume else "launch",
        "cwd": cwd,
        "exit_code": 0,
        **success_run_info,
    })
    if not json_flag:
        ctx["out"](f"{_goodbye_line(session, success_run_info, ctx['use_color'])}\n")
    if json_flag:
        extra = {"session": ctx["service"]["get_session"](session["name"]), "cwd": cwd}
        if capability:
            extra["resume"] = capability
        _write_json(ctx, _json_success("resume" if resume else "launch", message, warnings=warnings, **extra))
    return 0


def _goodbye_line(session, run_info, use_color):
    """One line printed when a session ends: cleanly, or by SIGINT/SIGTERM/SIGHUP.

    Not printed for a genuine provider crash (a nonzero exit that isn't one
    of those signals) - that path already gets its own error message.

    Local import: `commands.status` imports `handle_launch` from this module,
    so importing it back at module scope would be circular.
    """
    from .status import _format_duration_ms, _format_token_count, _format_usd

    parts = [f"Session {session['name']} ended", _format_duration_ms(run_info.get("duration_ms"))]
    usage = run_info.get("usage")
    cost = estimate_cost(usage, run_info.get("usage_model"))
    if cost is not None:
        parts.append(_format_usd(cost))
    elif isinstance(usage, dict):
        total_tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
        if total_tokens:
            parts.append(f"{_format_token_count(total_tokens)} tokens")
    return _dim(" · ".join(parts), use_color)


def _attach_interactive_usage(session, run_info, history=None):
    """Attach this run's own token usage without affecting launch outcome.

    Both interactive readers report a cumulative figure, so what a run *stores*
    has to be the increment over the previous run on the same transcript --
    otherwise a resumed session re-bills its whole history on every resume, and
    `cdx stats` sums that inflation again.

    The cumulative is kept beside the delta as `usage_cumulative`: it is the
    baseline the next run differences against, and without it a single run that
    recorded nothing would break the chain for every run after it.
    """
    run_info = dict(run_info or {})
    started_at = run_info.get("started_at")
    cumulative, provider_transcript, match, model = extract_interactive_usage(
        session.get("provider"), _get_auth_home(session), started_at, _conversation_id(session),
        # Ollama writes no provider transcript; its only record is the PTY
        # capture this run already took.
        run_info.get("transcript_path"),
    )
    if provider_transcript:
        run_info["provider_transcript_path"] = provider_transcript
        # How the transcript was found travels with the number. A recency match
        # is a guess that happened to be the newest file; recording it the same
        # way as an id match would let a wrong attribution read as a
        # measurement, which is the failure this replaced.
        run_info["provider_transcript_match"] = match
    if not cumulative:
        return run_info

    run_info["usage_cumulative"] = cumulative
    if model:
        # Which model actually served the run, read from the transcript rather
        # than inferred from the session's configured launch settings -- where
        # `model` is optional and usually unset, because the session takes the
        # provider's default.
        run_info["usage_model"] = model
    previous = _previous_cumulative(history, provider_transcript)
    if previous is not None:
        delta = usage_delta(cumulative, previous)
        if delta is not None:
            run_info["usage"] = delta
        # A None delta means the transcript shrank, rotated, or was replaced.
        # The baseline above still updates, so the next run recovers.
    elif not transcript_predates_run(provider_transcript, started_at):
        # First sighting of a transcript this run created: all of it is ours.
        run_info["usage"] = cumulative
    return run_info


def _previous_cumulative(history, transcript_path):
    """The cumulative the last run on this same transcript left behind."""
    if not history or not transcript_path:
        return None
    for entry in history:
        if entry.get("provider_transcript_path") != transcript_path:
            continue
        cumulative = entry.get("usage_cumulative")
        if isinstance(cumulative, dict):
            return cumulative
    return None

def _parse_handoff_args(rest):
    json_flag, args = _parse_json_flag(rest)
    names, flags = [], {}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("--"):
            key, sep, value = arg.partition("=")
            if key not in ("--source-conversation", "--source-transcript") or key in flags:
                raise CdxError(HANDOFF_USAGE)
            if not sep:
                index += 1
                value = args[index] if index < len(args) else ""
            if not value or value.startswith("--"):
                raise CdxError(HANDOFF_USAGE)
            flags[key] = value
        else:
            names.append(arg)
        index += 1
    if len(names) not in (1, 2) or (flags and len(names) != 2) or len(flags) > 1:
        raise CdxError(HANDOFF_USAGE)
    return json_flag, names, flags


def _handoff_source(source, workspace, flags, ctx, json_flag):
    try:
        return resolve_source(source, workspace, flags.get("--source-conversation"), flags.get("--source-transcript"))
    except HandoffSourceError as error:
        candidates = error.candidates
        # JSON and non-interactive callers always make an explicit second call.
        if json_flag or not ctx["stdin_is_tty"] or not candidates or flags:
            raise
        ctx["out"](str(error) + "\n" + "".join(
            f"  {i + 1}. {c['conversation_id']} | {c['workspace']} | last event {c['last_event_at'] or 'unknown'}\n"
            for i, c in enumerate(candidates)
        ))
        ask = ctx["options"].get("input") or input
        try:
            answer = ask("Source conversation number (blank to cancel): ").strip()
        except (KeyboardInterrupt, EOFError):
            raise CdxError("Handoff cancelled.", exit_code=130) from None
        if not answer:
            raise CdxError("Handoff cancelled.", exit_code=130) from None
        if not answer.isdigit() or not 1 <= int(answer) <= len(candidates):
            raise CdxError("Handoff cancelled: choose a listed source.") from None
        return resolve_source(source, workspace, candidates[int(answer) - 1]["conversation_id"])


def handle_handoff(rest, ctx):
    json_flag, names, flags = _parse_handoff_args(rest)
    target = ctx["service"]["get_session"](names[-1])
    if not target:
        raise CdxError(f"Unknown session: {names[-1]}")
    if not target.get("enabled", True):
        raise CdxError(f"Session is disabled: {target['name']}")
    workspace = os.path.realpath(ctx.get("cwd") or os.getcwd())
    if not os.path.isdir(workspace):
        raise CdxError(f"Invalid directory: {workspace}")
    base_dir = ctx["service"]["base_dir"]
    source = None
    if len(names) == 2:
        if names[0] == names[1]:
            raise CdxError("Source and target sessions must be different")
        source = ctx["service"]["get_session"](names[0])
        if not source:
            raise CdxError(f"Unknown session: {names[0]}")
        try:
            transcript = _handoff_source(source, workspace, flags, ctx, json_flag)
        except HandoffSourceError as error:
            if not json_flag:
                choices = "\n".join(f"  {c['conversation_id']} | {c['workspace']} | {c['last_event_at'] or 'unknown'}" for c in error.candidates)
                raise CdxError(str(error) + ("\nCandidates:\n" + choices if choices else "")) from error
            _write_json(ctx, _json_failure("handoff", "handoff_source_unresolved", str(error), candidates=error.candidates))
            return error.exit_code
        path, entry = prepare_entry(base_dir, target, workspace, source, transcript)
    else:
        prepared = load_entry(base_dir, target, workspace)
        path, entry = prepared if prepared else prepare_entry(base_dir, target, workspace)
    prompt = launch_prompt(path, entry)
    if json_flag:
        _write_json(ctx, _json_success(
            "handoff", f"Prepared {entry['mode']} handoff for {target['name']}",
            context={"target_path": path}, handoff=entry,
            source_session=entry['source'], target_session={"name": target['name'], "provider": target['provider']},
            source_transcript=(entry['transcript'] or {}).get('path'), launch_prompt=prompt,
        ))
        return 0
    ctx["out"](f"Handoff ready ({entry['mode']}): {path}\n")
    return handle_launch(target['name'], ctx, initial_prompt=prompt, directory=workspace)
