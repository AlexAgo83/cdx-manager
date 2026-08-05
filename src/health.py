import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote, unquote

from .cli_render import _pad_table, _style
from .config import PROVIDER_CODEX
from .provider_runtime import codex_auth_diagnostic
from .status_source import _extract_account_identity


def _encode(name):
    return quote(name, safe="")


def _state_file_path(base_dir, name):
    return os.path.join(base_dir, "state", f"{_encode(name)}.json")


def _profiles_dir(base_dir):
    return os.path.join(base_dir, "profiles")


def _issue(status, code, message, detail=None, repairable=False):
    return {
        "status": status,
        "code": code,
        "message": message,
        "detail": detail,
        "repairable": repairable,
    }


def collect_health_report(service, base_dir, env=None, spawn_sync=None):
    env = env or os.environ
    issues = []

    for command in ("codex", "claude"):
        path = shutil.which(command, path=env.get("PATH"))
        status = "OK" if path else "WARN"
        issues.append(_issue(status, f"{command}_cli", f"{command} CLI {'found' if path else 'not found'}", path))
        if path:
            issues.append(_provider_cli_version_issue(command, path, env, spawn_sync))

    rtk_path = shutil.which("rtk", path=env.get("PATH"))
    issues.append(_issue(
        "OK" if rtk_path else "WARN",
        "rtk_cli",
        "RTK CLI found" if rtk_path else "RTK CLI not found; assistants can still run normally but may use more context on noisy commands",
        rtk_path,
    ))

    logics_path = shutil.which("logics-manager", path=env.get("PATH"))
    issues.append(_issue(
        "OK" if logics_path else "WARN",
        "logics_manager_cli",
        (
            "logics-manager CLI found"
            if logics_path
            else "logics-manager CLI not found; Logics workflow guidance will not be auto-enabled"
        ),
        logics_path,
    ))

    script_bin = env.get("CDX_SCRIPT_BIN", "script")
    script_path = shutil.which(script_bin, path=env.get("PATH"))
    issues.append(_issue(
        "OK" if script_path else "WARN",
        "script_cli",
        _script_cli_message(script_bin, bool(script_path)),
        script_path,
    ))

    issues.append(_check_cdx_home(base_dir))
    sessions = service["list_sessions"]()
    session_names = {session["name"] for session in sessions}
    codex_diagnostics = []
    for session in sessions:
        name = session["name"]
        root = session.get("sessionRoot") or service["get_session_root"](name)
        if not os.path.isdir(root):
            issues.append(_issue("FAIL", "missing_profile", f"session {name} profile is missing", root))
        state_path = _state_file_path(base_dir, name)
        if not os.path.isfile(state_path):
            issues.append(_issue("FAIL", "missing_state", f"session {name} state file is missing", state_path, True))
        if session.get("provider") == PROVIDER_CODEX:
            diag = codex_auth_diagnostic(session, spawn_sync=spawn_sync, env_override=env)
            diag["observed_account"] = _recent_codex_observed_account(diag.get("auth_home"))
            codex_diagnostics.append((session, diag))
            issues.extend(_codex_auth_issues(session, diag))

    issues.extend(_codex_shared_account_id_issues(codex_diagnostics))
    issues.extend(_collect_profile_issues(base_dir, session_names))
    return {"base_dir": base_dir, "issues": issues, "summary": summarize_health(issues)}


def _provider_cli_version_issue(command, path, env, spawn_sync=None):
    result = _run_version_command(command, env, spawn_sync)
    raw = (result.get("stdout") or result.get("stderr") or "").strip()
    version = _extract_version(raw)
    detail = {
        "command": command,
        "path": path,
        "version": version,
        "raw": raw,
        "capabilities": _provider_capability_hints(command),
    }
    if version:
        return _issue("OK", f"{command}_cli_version", f"{command} CLI version detected: {version}", detail)
    return _issue("WARN", f"{command}_cli_version", f"{command} CLI version could not be detected", detail)


def _run_version_command(command, env, spawn_sync=None):
    try:
        if spawn_sync:
            result = spawn_sync(command, ["--version"], {"env": env, "timeout": 5})
            if isinstance(result, dict):
                return result
            return {
                "stdout": getattr(result, "stdout", "") or "",
                "stderr": getattr(result, "stderr", "") or "",
            }
        completed = subprocess.run(
            [command, "--version"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return {"stdout": completed.stdout or "", "stderr": completed.stderr or ""}
    except (OSError, subprocess.TimeoutExpired):
        return {"stdout": "", "stderr": ""}


def _extract_version(text):
    match = re.search(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b", text or "")
    return match.group(1) if match else None


def _provider_capability_hints(command):
    if command == "codex":
        return [
            "version_inventory",
            "provider_memory_import_surfaces_may_exist_in_recent_codex",
            "provider_memory_is_not_modified_by_cdx_memory",
        ]
    if command == "claude":
        return [
            "version_inventory",
            "project_memory_and_stream_json_diagnostics_may_exist_in_recent_claude_code",
            "provider_memory_is_not_modified_by_cdx_memory",
        ]
    return ["version_inventory"]


def _codex_auth_issues(session, diag):
    name = session["name"]
    identity = diag.get("account_email") or diag.get("observed_account") or "unknown account"
    issues = [
        _issue(
            "OK" if diag.get("auth_json_exists") else "WARN",
            "codex_auth_file",
            f"session {name} Codex auth file {'found' if diag.get('auth_json_exists') else 'missing'} ({identity})",
            {
                "session": name,
                "auth_home": diag.get("auth_home"),
                "auth_json_exists": diag.get("auth_json_exists"),
                "local_tokens_present": diag.get("local_tokens_present"),
                "account_email": diag.get("account_email"),
                "observed_account": diag.get("observed_account"),
                "account_id": _mask_identifier(diag.get("account_id")),
            },
        )
    ]
    live_status = diag.get("live_status")
    live_ok = live_status == "authenticated"
    live_warn = live_status in ("logged_out", "error")
    issues.append(_issue(
        "OK" if live_ok else "WARN" if live_warn else "WARN",
        "codex_live_auth",
        f"session {name} live Codex auth status: {live_status}",
        {
            "session": name,
            "auth_home": diag.get("auth_home"),
            "live_status": live_status,
            "live_error": diag.get("live_error"),
        },
    ))
    stale_auth = _recent_codex_auth_error(diag.get("auth_home"))
    if stale_auth:
        issues.append(_issue(
            "WARN",
            "codex_stale_auth_logs",
            f"session {name} recent Codex logs mention expired auth; run cdx login {name} if disconnects continue",
            {
                "session": name,
                "auth_home": diag.get("auth_home"),
                "source": stale_auth["source"],
                "mtime": stale_auth["mtime"],
                "markers": stale_auth["markers"],
            },
        ))
    return issues


def _codex_shared_account_id_issues(codex_diagnostics):
    by_account_id = {}
    for session, diag in codex_diagnostics:
        account_id = diag.get("account_id")
        if account_id:
            by_account_id.setdefault(account_id, []).append((session, diag))

    issues = []
    for account_id, rows in sorted(by_account_id.items()):
        if len(rows) < 2:
            continue
        identities = sorted({
            _identity_user_part(diag.get("account_email") or diag.get("observed_account"))
            for _session, diag in rows
            if _identity_user_part(diag.get("account_email") or diag.get("observed_account"))
        })
        sessions = [session["name"] for session, _diag in rows]
        status = "OK" if len(identities) > 1 else "WARN"
        message = (
            "Codex profiles share a Business account_id but observed different users; account_id is not a user identity"
            if status == "OK"
            else "Codex profiles share account_id; on Business plans this may be a workspace id, not proof of duplicate user auth"
        )
        issues.append(_issue(
            status,
            "codex_shared_account_id",
            message,
            {
                "sessions": sessions,
                "account_id": _mask_identifier(account_id),
                "observed_identities": identities,
            },
        ))
    return issues


def _identity_user_part(value):
    if not value:
        return None
    return str(value).strip().lower().split()[0].split("(", 1)[0]


def _mask_identifier(value):
    if not value:
        return None
    text = str(value)
    return text if len(text) <= 8 else f"{text[:6]}...{text[-4:]}"


def _recent_codex_observed_account(auth_home):
    for path in _recent_codex_log_paths(auth_home):
        text = _read_tail(path)
        account = _extract_account_identity(text)
        if account:
            return account
    return None


def _recent_codex_auth_error(auth_home):
    markers = ("token_expired", "authentication token is expired", "http 401")
    for path in _recent_codex_log_paths(auth_home):
        text = _read_tail(path).lower()
        found = [marker for marker in markers if marker in text]
        if found:
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat().replace("+00:00", "Z")
            except OSError:
                mtime = None
            return {"source": path, "mtime": mtime, "markers": found}
    return None


def _recent_codex_log_paths(auth_home):
    if not auth_home:
        return []
    candidates = []
    for root in (os.path.join(auth_home, "log"), os.path.join(auth_home, "sessions")):
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in {"cache", "plugins", "skills", "sqlite"}]
            for filename in filenames:
                if filename.endswith((".log", ".jsonl")):
                    path = os.path.join(dirpath, filename)
                    try:
                        stat = os.stat(path)
                    except OSError:
                        continue
                    candidates.append((stat.st_mtime, path))
    return [path for _mtime, path in sorted(candidates, reverse=True)[:16]]


def _read_tail(path, max_bytes=128 * 1024):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _check_cdx_home(base_dir):
    try:
        os.makedirs(base_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix=".cdx-doctor.", dir=base_dir)
        os.close(fd)
        os.unlink(path)
        return _issue("OK", "cdx_home_writable", "CDX_HOME is writable", base_dir)
    except OSError as error:
        return _issue("FAIL", "cdx_home_writable", "CDX_HOME is not writable", f"{base_dir}: {error}")


def _script_cli_message(script_bin, is_available):
    if is_available:
        return f"{script_bin} CLI found"
    if sys.platform == "win32":
        return (
            f"{script_bin} CLI not found; Codex will launch without transcript capture "
            f"(expected on many Windows setups)"
        )
    return f"{script_bin} CLI not found; Codex will launch without transcript fallback"


def _collect_profile_issues(base_dir, session_names):
    profile_dir = _profiles_dir(base_dir)
    if not os.path.isdir(profile_dir):
        return []
    issues = []
    encoded_session_names = {_encode(name) for name in session_names}
    for entry in sorted(os.listdir(profile_dir)):
        path = os.path.join(profile_dir, entry)
        if not os.path.isdir(path):
            continue
        if entry.startswith(".") and ".remove." in entry:
            issues.append(_issue("WARN", "quarantine_profile", f"pending quarantine profile: {entry}", path, True))
            continue
        if entry.startswith("."):
            continue
        if entry not in encoded_session_names:
            issues.append(_issue("WARN", "orphan_profile", f"orphan profile: {unquote(entry)}", path, True))
    return issues


def summarize_health(issues):
    return {
        "ok": sum(1 for issue in issues if issue["status"] == "OK"),
        "warn": sum(1 for issue in issues if issue["status"] == "WARN"),
        "fail": sum(1 for issue in issues if issue["status"] == "FAIL"),
        "repairable": sum(1 for issue in issues if issue.get("repairable")),
    }


def filter_health_report(report, severity):
    if severity is None:
        return report
    severities = set(severity.split(","))
    issues = [issue for issue in report["issues"] if issue["status"] in severities]
    return {
        **report,
        "issues": issues,
        "summary": summarize_health(issues),
        "severity": severity,
    }


def format_health_report(report, use_color=False):
    rows = [["STATUS", "CHECK", "MESSAGE"]]
    for issue in report["issues"]:
        status = issue["status"]
        style = "32" if status == "OK" else "33" if status == "WARN" else "31"
        rows.append([_style(status, style, use_color), issue["code"], issue["message"]])
    summary = report["summary"]
    return "\n".join([
        _pad_table(rows),
        "",
        _style(
            f"Summary: {summary['ok']} OK, {summary['warn']} WARN, {summary['fail']} FAIL, {summary['repairable']} repairable.",
            "1",
            use_color,
        ),
    ])


def health_json(report):
    return json.dumps(report, indent=2)
