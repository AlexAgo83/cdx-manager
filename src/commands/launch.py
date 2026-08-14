"""Launch domain commands: launch, resume, can-resume, handoff.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import os
import shlex

from ..agent_notify import notifications_enabled, provision, supports_agent_alerts
from ..cli_args import CAN_RESUME_USAGE, HANDOFF_USAGE, RESUME_USAGE, _parse_json_flag
from ..cli_helpers import (
    API_SCHEMA_VERSION,
    _build_handoff_context,
    _handoff_launch_prompt,
    _json_success,
    _latest_handoff_transcript_path,
    _read_handoff_transcript,
    _resume_capability_for_session,
    _update_notice_warnings,
    _warn_if_session_already_running,
    _write_json,
    _write_update_notice,
)
from ..cli_render import _dim, _info, _success, _warn
from ..config import PROVIDER_CODEX
from ..context_store import install_context_for_session, write_context
from ..errors import CdxError
from ..interactive_usage import extract_interactive_usage, transcript_predates_run, usage_delta
from ..provider_runtime import _ensure_session_authentication, _get_auth_home, _run_interactive_provider_command


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
    session = ctx["service"]["launch_session"](command)
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
        **_attach_interactive_usage(
            session, run_info, ctx["service"]["get_launch_history"](session["name"], limit=50)
        ),
    })
    if json_flag:
        extra = {"session": ctx["service"]["get_session"](session["name"]), "cwd": cwd}
        if capability:
            extra["resume"] = capability
        _write_json(ctx, _json_success("resume" if resume else "launch", message, warnings=warnings, **extra))
    return 0


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
    cumulative, provider_transcript = extract_interactive_usage(
        session.get("provider"), _get_auth_home(session), started_at
    )
    if provider_transcript:
        run_info["provider_transcript_path"] = provider_transcript
    if not cumulative:
        return run_info

    run_info["usage_cumulative"] = cumulative
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
