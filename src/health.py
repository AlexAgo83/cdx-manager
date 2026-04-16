import json
import os
import shutil
import tempfile
from urllib.parse import quote, unquote

from .cli_render import _pad_table, _style


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


def collect_health_report(service, base_dir, env=None):
    env = env or os.environ
    issues = []

    for command in ("codex", "claude"):
        path = shutil.which(command, path=env.get("PATH"))
        status = "OK" if path else "WARN"
        issues.append(_issue(status, f"{command}_cli", f"{command} CLI {'found' if path else 'not found'}", path))

    script_bin = env.get("CDX_SCRIPT_BIN", "script")
    script_path = shutil.which(script_bin, path=env.get("PATH"))
    issues.append(_issue(
        "OK" if script_path else "WARN",
        "script_cli",
        f"{script_bin} CLI {'found' if script_path else 'not found; Codex will launch without transcript fallback'}",
        script_path,
    ))

    issues.append(_check_cdx_home(base_dir))
    sessions = service["list_sessions"]()
    session_names = {session["name"] for session in sessions}
    for session in sessions:
        name = session["name"]
        root = session.get("sessionRoot") or service["get_session_root"](name)
        if not os.path.isdir(root):
            issues.append(_issue("FAIL", "missing_profile", f"session {name} profile is missing", root))
        state_path = _state_file_path(base_dir, name)
        if not os.path.isfile(state_path):
            issues.append(_issue("FAIL", "missing_state", f"session {name} state file is missing", state_path, True))

    issues.extend(_collect_profile_issues(base_dir, session_names))
    return {"base_dir": base_dir, "issues": issues, "summary": summarize_health(issues)}


def _check_cdx_home(base_dir):
    try:
        os.makedirs(base_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix=".cdx-doctor.", dir=base_dir)
        os.close(fd)
        os.unlink(path)
        return _issue("OK", "cdx_home_writable", "CDX_HOME is writable", base_dir)
    except OSError as error:
        return _issue("FAIL", "cdx_home_writable", "CDX_HOME is not writable", f"{base_dir}: {error}")


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
