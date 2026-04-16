import json
import os
import shutil

from .health import collect_health_report


def repair_health(service, base_dir, env=None, dry_run=True, force=False):
    report = collect_health_report(service, base_dir, env)
    actions = []
    for issue in report["issues"]:
        code = issue["code"]
        detail = issue.get("detail")
        if code == "missing_state":
            name = _session_name_from_state_path(detail)
            actions.append(_action(
                "recreate_state",
                f"recreate missing state for {name}",
                detail,
                _apply_recreate_state(service, name) if not dry_run else None,
            ))
        elif code == "quarantine_profile":
            actions.append(_action(
                "remove_quarantine",
                f"remove quarantine profile {os.path.basename(detail)}",
                detail,
                _apply_remove_path(detail) if not dry_run else None,
            ))
        elif code == "orphan_profile":
            if force:
                actions.append(_action(
                    "quarantine_orphan",
                    f"move orphan profile {os.path.basename(detail)} to quarantine",
                    detail,
                    _apply_quarantine_orphan(detail) if not dry_run else None,
                ))
            else:
                actions.append(_action(
                    "skip_orphan",
                    f"orphan profile needs --force: {os.path.basename(detail)}",
                    detail,
                    "skipped",
                ))
    return {
        "dry_run": dry_run,
        "force": force,
        "actions": actions,
        "summary": {
            "planned": len(actions),
            "applied": sum(1 for action in actions if action["status"] == "applied"),
            "skipped": sum(1 for action in actions if action["status"] == "skipped"),
        },
    }


def _session_name_from_state_path(path):
    if not path:
        return None
    filename = os.path.basename(path)
    if filename.endswith(".json"):
        filename = filename[:-5]
    from urllib.parse import unquote
    return unquote(filename)


def _apply_recreate_state(service, name):
    service["ensure_session_state"](name)
    return "applied"


def _apply_remove_path(path):
    shutil.rmtree(path)
    return "applied"


def _apply_quarantine_orphan(path):
    parent = os.path.dirname(path)
    dest = os.path.join(parent, f".{os.path.basename(path)}.remove.orphan")
    suffix = 1
    candidate = dest
    while os.path.exists(candidate):
        suffix += 1
        candidate = f"{dest}.{suffix}"
    os.rename(path, candidate)
    return "applied"


def _action(code, message, path, result):
    if result is None:
        status = "planned"
    elif result == "skipped":
        status = "skipped"
    else:
        status = "applied"
    return {"status": status, "code": code, "message": message, "path": path}


def format_repair_report(report, use_color=False):
    from .cli_render import _pad_table, _style

    rows = [["STATUS", "ACTION", "MESSAGE"]]
    for action in report["actions"]:
        status = action["status"]
        style = "32" if status == "applied" else "33" if status == "planned" else "2"
        rows.append([_style(status.upper(), style, use_color), action["code"], action["message"]])
    if len(rows) == 1:
        rows.append([_style("OK", "32", use_color), "-", "nothing to repair"])
    summary = report["summary"]
    return "\n".join([
        _pad_table(rows),
        "",
        _style(
            f"Summary: {summary['planned']} planned, {summary['applied']} applied, {summary['skipped']} skipped.",
            "1",
            use_color,
        ),
    ])


def repair_json(report):
    return json.dumps(report, indent=2)
