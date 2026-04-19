import json
import os
import signal
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from .errors import CdxError


LOG_ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB


def _home_env_overrides(auth_home):
    """Return env vars that point the claude CLI to the given home directory.

    On Unix, only HOME is needed.  On Windows, Node.js resolves the home
    directory via USERPROFILE (and falls back to HOMEDRIVE+HOMEPATH), so we
    set all three to ensure profile isolation works regardless of the platform.
    """
    overrides = {"HOME": auth_home}
    if sys.platform == "win32":
        overrides["USERPROFILE"] = auth_home
        overrides["HOMEDRIVE"] = os.path.splitdrive(auth_home)[0] or "C:"
        overrides["HOMEPATH"] = os.path.splitdrive(auth_home)[1] or auth_home
    return overrides


def _get_auth_home(session):
    return session.get("authHome") or session.get("sessionRoot") or session.get("codexHome", "")


def _get_launch_transcript_path(session):
    return os.path.join(_get_auth_home(session), "log", "cdx-session.log")


def _get_launch_transcript_dir(session):
    return os.path.join(_get_auth_home(session), "log")


def _build_launch_transcript_path(session):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return os.path.join(
        _get_launch_transcript_dir(session),
        f"cdx-session-{stamp}-{os.getpid()}.log",
    )


def _list_launch_transcript_paths(session, glob_fn=None):
    import glob

    glob_fn = glob_fn or glob.glob
    log_dir = _get_launch_transcript_dir(session)
    if not os.path.isdir(log_dir):
        return []
    paths = set(glob_fn(os.path.join(log_dir, "cdx-session*.log")))
    legacy = _get_launch_transcript_path(session)
    if os.path.exists(legacy):
        paths.add(legacy)
    return sorted(paths)


def _rotate_log_if_needed(log_path):
    try:
        if os.path.getsize(log_path) >= LOG_ROTATE_BYTES:
            open(log_path, "w").close()
    except OSError:
        pass


def _wrap_launch_with_transcript(session, spec, capture_transcript=True, env=None):
    if not capture_transcript:
        return spec
    env = env or os.environ
    script_bin = env.get("CDX_SCRIPT_BIN", "script")
    script_args = env.get("CDX_SCRIPT_ARGS")
    transcript_path = _build_launch_transcript_path(session)
    os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
    _rotate_log_if_needed(transcript_path)
    if script_args:
        args = shlex.split(script_args)
        if "{transcript}" in args:
            args = [transcript_path if arg == "{transcript}" else arg for arg in args]
        else:
            args = args + [transcript_path]
        args = args + [spec["command"]] + spec["args"]
    else:
        args = ["-q", "-F", transcript_path, spec["command"]] + spec["args"]
    return {
        "command": script_bin,
        "args": args,
        "options": spec["options"],
        "label": spec["label"],
        "fallback": spec,
        "transcript_path": transcript_path,
    }


def _build_launch_spec(session, cwd=None, env_override=None):
    cwd = cwd or os.getcwd()
    env_override = env_override or {}
    env = {**os.environ, **env_override}
    if session["provider"] == "claude":
        return {
            "command": "claude",
            "args": ["--name", session["name"]],
            "options": {
                "cwd": cwd,
                "env": {**env, **_home_env_overrides(_get_auth_home(session))},
            },
            "label": "claude",
        }
    return _wrap_launch_with_transcript(session, {
        "command": "codex",
        "args": ["--no-alt-screen", "--cd", cwd],
        "options": {
            "env": {**env, "CODEX_HOME": _get_auth_home(session)},
        },
        "label": "codex",
    }, env=env)


def _build_login_status_spec(session, env_override=None):
    env = {**os.environ, **(env_override or {})}
    if session["provider"] == "claude":
        env.update(_home_env_overrides(_get_auth_home(session)))

        def parser(output):
            try:
                return bool(json.loads(output or "{}").get("loggedIn"))
            except (json.JSONDecodeError, AttributeError):
                return False

        return {"command": "claude", "args": ["auth", "status"], "env": env,
                "parser": parser, "label": "claude auth status"}
    env["CODEX_HOME"] = _get_auth_home(session)

    def parser(output):
        if "Not logged in" in (output or ""):
            return False
        return "Logged in" in (output or "")

    return {"command": "codex", "args": ["login", "status"], "env": env,
            "parser": parser, "label": "codex login status"}


def _build_auth_action_spec(session, action, cwd=None, env_override=None):
    cwd = cwd or os.getcwd()
    env = {**os.environ, **(env_override or {})}
    if session["provider"] == "claude":
        env.update(_home_env_overrides(_get_auth_home(session)))
        return {"command": "claude", "args": ["auth", action],
                "options": {"cwd": cwd, "env": env}, "label": f"claude auth {action}"}
    env["CODEX_HOME"] = _get_auth_home(session)
    return {"command": "codex", "args": [action],
            "options": {"cwd": cwd, "env": env}, "label": f"codex {action}"}


def _format_probe_failure(session, spec, error):
    command = spec["command"]
    if isinstance(error, FileNotFoundError):
        return CdxError(
            f"Failed to check login status for {session['name']}: {command} CLI not found on PATH. "
            f"Install {command} and retry cdx add {session['name']}.",
            127,
        )
    message = getattr(error, "message", None) or str(error)
    return CdxError(f"Failed to check login status for {session['name']}: {message}")


def _resolve_command(command, env=None):
    env = env or os.environ
    return shutil.which(command, path=env.get("PATH")) or command


def _probe_provider_auth(session, spawn_sync=None, env_override=None):
    spawn_sync = spawn_sync or subprocess.run
    spec = _build_login_status_spec(session, env_override)
    if session.get("provider") == "codex":
        auth_path = os.path.join(_get_auth_home(session), "auth.json")
        if os.path.isfile(auth_path):
            return True
    try:
        if spawn_sync is subprocess.run:
            command = _resolve_command(spec["command"], spec["env"])
            result = subprocess.run(
                [command] + spec["args"],
                env=spec["env"],
                capture_output=True, text=True,
            )
            output = (result.stdout or "") + (result.stderr or "")
        else:
            result = spawn_sync(spec["command"], spec["args"], spec)
            error = result.get("error") if isinstance(result, dict) else getattr(result, "error", None)
            if error:
                raise _format_probe_failure(session, spec, error)
            stdout = result.get("stdout") if isinstance(result, dict) else getattr(result, "stdout", "")
            stderr = result.get("stderr") if isinstance(result, dict) else getattr(result, "stderr", "")
            output = (stdout or "") + (stderr or "")
    except FileNotFoundError as error:
        raise _format_probe_failure(session, spec, error)
    return spec["parser"](output)


def _signal_exit_code(sig):
    mapping = {signal.SIGINT: 130, signal.SIGTERM: 143}
    if hasattr(signal, "SIGHUP"):
        mapping[signal.SIGHUP] = 129
    return mapping.get(sig, 1)


def _signal_name(sig):
    if hasattr(sig, "name"):
        return sig.name
    try:
        return signal.Signals(sig).name
    except (TypeError, ValueError):
        return str(sig)


def _run_interactive_provider_command(session, action, spawn=None, cwd=None,
                                      env_override=None, signal_emitter=None):
    spawn = spawn or subprocess.Popen
    spec = (
        _build_launch_spec(session, cwd=cwd, env_override=env_override)
        if action == "launch"
        else _build_auth_action_spec(session, action, cwd=cwd, env_override=env_override)
    )
    def start_child(current_spec):
        command = current_spec["command"]
        if spawn is subprocess.Popen:
            command = _resolve_command(command, current_spec.get("options", {}).get("env"))
        return spawn(
            [command] + current_spec["args"],
            **{k: v for k, v in current_spec.get("options", {}).items() if k != "stdio"},
        )

    try:
        child = start_child(spec)
    except FileNotFoundError as error:
        spec = _fallback_launch_spec_or_raise(spec, error)
        child = start_child(spec)

    forwarded_signal = [None]
    handlers = []

    def forward(sig, _frame=None):
        forwarded_signal[0] = sig
        try:
            if hasattr(child, "send_signal"):
                child.send_signal(sig)
            elif hasattr(child, "kill"):
                child.kill(sig)
        except Exception:
            pass

    original_handlers = {}
    use_emitter = hasattr(signal_emitter, "on") and hasattr(signal_emitter, "removeListener")

    if use_emitter:
        for sig in ("SIGINT", "SIGTERM", "SIGHUP"):
            handler = lambda current_sig=sig: forward(getattr(signal, current_sig), None)
            handlers.append((sig, handler))
            signal_emitter.on(sig, handler)
    else:
        _forward_sigs = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGHUP"):
            _forward_sigs.append(signal.SIGHUP)
        for sig in _forward_sigs:
            try:
                original_handlers[sig] = signal.signal(sig, forward)
            except (OSError, ValueError):
                pass

    try:
        child.wait()
        if forwarded_signal[0] is None and child.returncode != 0 and _should_retry_without_transcript(spec):
            spec = _fallback_launch_spec_or_raise(spec)
            child = start_child(spec)
            child.wait()
    finally:
        if use_emitter:
            for sig, handler in handlers:
                try:
                    signal_emitter.removeListener(sig, handler)
                except Exception:
                    pass
        else:
            for sig, handler in original_handlers.items():
                try:
                    signal.signal(sig, handler)
                except (OSError, ValueError):
                    pass

    if forwarded_signal[0] is not None:
        raise CdxError(
            f"{spec['label']} interrupted by {_signal_name(forwarded_signal[0])} for session {session['name']}",
            _signal_exit_code(forwarded_signal[0]),
        )
    if child.returncode != 0:
        raise CdxError(
            f"{spec['label']} exited with code {child.returncode} for session {session['name']}"
        )


def _fallback_launch_spec_or_raise(spec, original_error=None):
    fallback = spec.get("fallback")
    if not fallback:
        if original_error is not None:
            raise original_error
        raise CdxError(f"{spec['label']} cannot run without a fallback")
    return {**fallback, "label": f"{fallback['label']} (without transcript)"}


def _should_retry_without_transcript(spec):
    if not spec.get("fallback"):
        return False
    transcript_path = spec.get("transcript_path")
    if not transcript_path:
        return False
    try:
        return not os.path.exists(transcript_path) or os.path.getsize(transcript_path) == 0
    except OSError:
        return True


def _ensure_session_authentication(session, service, spawn=None, spawn_sync=None,
                                   stdin_is_tty=True, env_override=None, behavior="launch",
                                   signal_emitter=None):
    is_authenticated = _probe_provider_auth(session, spawn_sync=spawn_sync, env_override=env_override)
    if is_authenticated:
        return {"authenticated": True, "checked": True}
    if behavior == "probe-only":
        return {"authenticated": False, "checked": True}
    if behavior == "launch":
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    if not stdin_is_tty:
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    _run_interactive_provider_command(
        session, "login", spawn=spawn, env_override=env_override, signal_emitter=signal_emitter
    )
    return {"authenticated": True, "checked": True, "bootstrapped": True}
