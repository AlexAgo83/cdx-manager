"""Maintenance domain commands: doctor, repair, clean, disk, update.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime

from ..cli_args import DISK_USAGE, REPAIR_USAGE, _parse_doctor_args, _parse_flag_args, _parse_json_flag, _parse_update_args
from ..cli_helpers import _format_bytes, _json_success, _resolve_confirmation, _write_json
from ..cli_render import _dim, _info, _pad_table, _style, _success, _warn
from ..errors import CdxError
from ..health import collect_health_report, filter_health_report, format_health_report
from ..provider_runtime import _list_launch_transcript_paths
from ..repair import format_repair_report, repair_health
from ..update_all import apply_update_all_plan, collect_update_all_plan
from ..update_check import LatestReleaseCheckError, fetch_latest_release, fetch_latest_release_or_raise, is_newer_version
from ..update_manager import build_update_plan, format_update_failure, run_update_plan, verify_updated_command


def _format_update_all(plan, use_color=False):
    labels = {
        "up_to_date": _success("OK", use_color),
        "update_available": _warn("UPDATE", use_color),
        "not_installed": _warn("MISSING", use_color),
        "check_with_native_updater": _info("CHECK", use_color),
    }
    rows = [[_style("TOOL", "1", use_color), _style("CURRENT", "1", use_color), _style("LATEST", "1", use_color), _style("STATUS", "1", use_color)]]
    for item in plan["items"]:
        rows.append([_info(item["name"], use_color), item.get("version") or _dim("-", use_color), item.get("latest_version") or _dim("-", use_color), labels.get(item["status"], item["status"].replace("_", " "))])
    lines = [_style("Workstation update", "1", use_color), _dim("Inventory only — nothing has changed.", use_color), "", _pad_table(rows)]
    missing_rtk = plan["setup"]["rtk_missing_sessions"]
    setup = [f"RTK: enable for {', '.join(missing_rtk)}" if missing_rtk else "RTK: configured for every session"]
    setup.extend(f"Ponytail {plugin['session']}: {labels.get(plugin['status'], plugin['status'].replace('_', ' '))}" for plugin in plan["setup"]["ponytail"])
    lines.extend(["", _style("Session setup", "1", use_color), *setup])
    if plan["steps"]:
        lines.extend(["", _warn(f"{len(plan['steps'])} action(s) ready", use_color), _dim("Confirm to update only the tools listed above.", use_color)])
    else:
        lines.extend(["", _success("Everything managed by CDX is current and configured.", use_color)])
    return "\n".join(lines)

def _format_update_all_result(result, use_color=False):
    if result.get("skipped"):
        return _warn(f"skipped: {result['name']} (blocked by {result['blocked_by']})", use_color)
    if result.get("returncode") == 0:
        return _success(f"done: {result['name']}", use_color)
    detail = str(result.get("stderr") or result.get("stdout") or "No error output.").strip().replace("\n", " ")
    detail = detail[-500:]
    command = shlex.join(result.get("command") or [])
    suffix = f"\n  {_dim(command, use_color)}" if command else ""
    label = _warn(f"failed: {result['name']} (exit {result.get('returncode')})", use_color)
    return f"{label}\n  {detail}{suffix}"

def _confirm_profile_cleanup(action):
    answer = input(f"Delete matching profile {action} candidates? [y/N] ")
    return answer.strip().lower() in ("y", "yes")

def _confirm_log_cleanup(target):
    answer = input(f"Clear launch transcript logs for {target}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")

def _directory_size_bytes(path, runner=None):
    if not os.path.exists(path):
        raise CdxError(f"CDX home does not exist: {path}")
    runner = runner or subprocess.check_output
    try:
        output = runner(["du", "-sk", path], text=True, stderr=subprocess.DEVNULL)
        return int(str(output).split()[0]) * 1024
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        total = 0
        for root, _, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return total

def _directory_child_sizes(path, runner=None, progress=None):
    rows = []
    try:
        names = os.listdir(path)
    except OSError:
        return rows
    children = [(name, os.path.join(path, name)) for name in names if os.path.isdir(os.path.join(path, name))]
    for index, (name, child_path) in enumerate(children, start=1):
        if progress:
            progress("profile", name, index, len(children))
        rows.append({
            "name": name,
            "path": child_path,
            "bytes": _directory_size_bytes(child_path, runner=runner),
        })
    rows.sort(key=lambda row: row["bytes"], reverse=True)
    for row in rows:
        row["size"] = _format_bytes(row["bytes"])
    return rows

def _parse_days(value, usage):
    match = re.fullmatch(r"(\d+)(?:d)?", str(value or "").strip())
    if not match or int(match.group(1)) <= 0:
        raise CdxError(usage)
    return int(match.group(1))

def _candidate(profile, kind, path, bytes_used, reason, risk="safe", evidence=None):
    return {
        "profile": profile,
        "kind": kind,
        "path": path,
        "bytes": bytes_used,
        "size": _format_bytes(bytes_used),
        "reason": reason,
        "risk": risk,
        "evidence": evidence or {},
    }

def _iter_profile_dirs(base_dir):
    profiles_dir = os.path.join(base_dir, "profiles")
    try:
        names = sorted(os.listdir(profiles_dir))
    except OSError:
        return
    for name in names:
        path = os.path.join(profiles_dir, name)
        if os.path.isdir(path):
            yield name, path

def _collect_old_logs(profile_name, profile_path, days, now=None):
    cutoff = (time.time() if now is None else now) - (days * 86400)
    paths = []
    bytes_used = 0
    latest_mtime = 0
    for root, _, files in os.walk(profile_path):
        if os.path.basename(root) != "log":
            continue
        for filename in files:
            if not filename.endswith(".log"):
                continue
            path = os.path.join(root, filename)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            if stat.st_mtime >= cutoff:
                continue
            paths.append(path)
            bytes_used += stat.st_size
            latest_mtime = max(latest_mtime, stat.st_mtime)
    if not paths:
        return None
    return _candidate(
        profile_name,
        f"old-logs-{days}d",
        profile_path,
        bytes_used,
        f"{len(paths)} .log files older than {days}d",
        risk="review",
        evidence={
            "days": days,
            "file_count": len(paths),
            "newest_old_log_mtime": datetime.fromtimestamp(latest_mtime).isoformat() if latest_mtime else None,
            "sample_paths": paths[:5],
        },
    )

def _collect_profile_cleanup_candidates(base_dir, *, old_log_days=30, runner=None, now=None, progress=None):
    candidates = []
    profiles = list(_iter_profile_dirs(base_dir))
    for index, (profile_name, profile_path) in enumerate(profiles, start=1):
        if progress:
            progress("candidates", profile_name, index, len(profiles))
        tmp_dir = os.path.join(profile_path, ".tmp")
        tmp_targets = [
            ("tmp-marketplaces", os.path.join(tmp_dir, "marketplaces"), "temporary marketplace cache/staging"),
        ]
        try:
            tmp_names = os.listdir(tmp_dir)
        except OSError:
            tmp_names = []
        for name in tmp_names:
            if name.startswith("plugins-clone-"):
                tmp_targets.append(("tmp-plugin-clone", os.path.join(tmp_dir, name), "temporary plugin clone"))
            elif name.startswith("plugins-backup-"):
                tmp_targets.append(("tmp-plugin-backup", os.path.join(tmp_dir, name), "temporary plugin backup"))
        for kind, path, reason in tmp_targets:
            if not os.path.exists(path):
                continue
            bytes_used = _directory_size_bytes(path, runner=runner)
            if bytes_used <= 0:
                continue
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
            except OSError:
                mtime = None
            candidates.append(_candidate(
                profile_name,
                kind,
                path,
                bytes_used,
                reason,
                evidence={"modified_at": mtime},
            ))
        old_logs = _collect_old_logs(profile_name, profile_path, old_log_days, now=now)
        if old_logs and old_logs["bytes"] > 0:
            candidates.append(old_logs)
    candidates.sort(key=lambda item: item["bytes"], reverse=True)
    return candidates

def _format_cleanup_candidates(candidates, use_color=False):
    if not candidates:
        return _dim("No cleanup candidates found.", use_color)
    reclaimable = sum(item["bytes"] for item in candidates)
    lines = [
        _style("Cleanup candidates", "1", use_color),
        f"{_style(_format_bytes(reclaimable), '33', use_color)} reclaimable across {len({item['profile'] for item in candidates})} profile(s)",
    ]
    by_profile = {}
    for item in candidates:
        by_profile.setdefault(item["profile"], []).append(item)
    for profile, items in sorted(by_profile.items(), key=lambda row: sum(i["bytes"] for i in row[1]), reverse=True):
        total = sum(item["bytes"] for item in items)
        lines.extend(["", f"{_style(profile, '1', use_color)}  {_style(_format_bytes(total), '33', use_color)}"])
        rows = [[
            _style("SIZE", "1", use_color),
            _style("TYPE", "1", use_color),
            _style("RISK", "1", use_color),
            _style("EVIDENCE", "1", use_color),
        ]]
        for item in items:
            risk_color = "32" if item["risk"] == "safe" else "33"
            rows.append([
                _style(item["size"], "36", use_color),
                item["kind"],
                _style(item["risk"], risk_color, use_color),
                item["reason"],
            ])
        lines.append(_pad_table(rows))
    return "\n".join(lines)

def _format_disk_report(payload, use_color=False):
    title = "CDX profiles" if payload["target"] == "profiles" else "CDX home"
    lines = [
        _style(title, "1", use_color),
        f"Path:  {_dim(payload['path'], use_color)}",
        f"Total: {_style(payload['size'], '36', use_color)}",
    ]
    children = payload.get("children") or []
    if children:
        reclaimable_by_profile = {}
        for item in payload.get("candidates") or []:
            reclaimable_by_profile[item["profile"]] = reclaimable_by_profile.get(item["profile"], 0) + item["bytes"]
        headers = ["PROFILE", "SIZE", "SHARE"]
        if "candidates" in payload:
            headers.append("RECLAIMABLE")
        rows = [[_style(header, "1", use_color) for header in headers]]
        for child in children:
            share = (child["bytes"] / payload["bytes"] * 100) if payload["bytes"] else 0
            row = [
                _style(child["name"], "1", use_color),
                _style(child["size"], "36", use_color),
                f"{share:.1f}%",
            ]
            if "candidates" in payload:
                reclaimable = reclaimable_by_profile.get(child["name"], 0)
                row.append(_style(_format_bytes(reclaimable), "33", use_color) if reclaimable else _dim("-", use_color))
            rows.append(row)
        lines.extend(["", _style(f"Profiles ({len(children)})", "1", use_color), _pad_table(rows)])
    if "candidates" in payload:
        lines.extend(["", _format_cleanup_candidates(payload["candidates"], use_color=use_color)])
    return "\n".join(lines)

def _remove_path(path):
    try:
        if os.path.isdir(path):
            size = _directory_size_bytes(path)
            shutil.rmtree(path)
        else:
            size = os.path.getsize(path)
            os.remove(path)
        return size
    except OSError as error:
        raise CdxError(f"Failed to remove cleanup candidate {path}: {error}") from error

def _clean_profile_tmp(profile_path):
    tmp_dir = os.path.join(profile_path, ".tmp")
    targets = [os.path.join(tmp_dir, "marketplaces")]
    try:
        names = os.listdir(tmp_dir)
    except OSError:
        names = []
    targets.extend(os.path.join(tmp_dir, name) for name in names if name.startswith(("plugins-clone-", "plugins-backup-")))
    freed = 0
    removed = []
    for path in targets:
        if os.path.exists(path):
            size = _remove_path(path)
            if size:
                freed += size
                removed.append(path)
    return freed, removed

def _clean_profile_old_logs(profile_path, days, now=None):
    cutoff = (time.time() if now is None else now) - (days * 86400)
    freed = 0
    removed = []
    for root, _, files in os.walk(profile_path):
        if os.path.basename(root) != "log":
            continue
        for filename in files:
            if not filename.endswith(".log"):
                continue
            path = os.path.join(root, filename)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            if stat.st_mtime >= cutoff:
                continue
            try:
                os.remove(path)
            except OSError as error:
                raise CdxError(f"Failed to remove old log {path}: {error}") from error
            freed += stat.st_size
            removed.append(path)
    return freed, removed

def _handle_clean_profiles(args, ctx, json_flag):
    usage = "Usage: cdx clean profiles (--tmp|--old-logs DAYS) [--yes] [--json]"
    yes = "--yes" in args
    args = [arg for arg in args if arg != "--yes"]
    clean_tmp = "--tmp" in args
    old_logs = None
    if "--old-logs" in args:
        index = args.index("--old-logs")
        if index + 1 >= len(args):
            raise CdxError(usage)
        old_logs = _parse_days(args[index + 1], usage)
        args = [arg for i, arg in enumerate(args) if i not in (index, index + 1)]
    else:
        old_log_equals = [arg for arg in args if arg.startswith("--old-logs=")]
        if old_log_equals:
            if len(old_log_equals) > 1:
                raise CdxError(usage)
            old_logs = _parse_days(old_log_equals[0].split("=", 1)[1], usage)
            args = [arg for arg in args if arg != old_log_equals[0]]
    args = [arg for arg in args if arg != "--tmp"]
    if args or clean_tmp == (old_logs is not None):
        raise CdxError(usage)

    action = "temporary cache" if clean_tmp else f"logs older than {old_logs}d"
    if not yes:
        confirm_fn = ctx["options"].get("confirmProfileCleanup")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, action)
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Profile cleanup requires an interactive terminal or --yes in non-interactive mode.")
        else:
            confirmed = _confirm_profile_cleanup(action)
        if not confirmed:
            if json_flag:
                _write_json(ctx, _json_success("clean.profiles", "Cancelled.", cancelled=True, freed_bytes=0, freed_size="0 B", profiles=[]))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0

    results = []
    now = ctx["options"].get("now")() if callable(ctx["options"].get("now")) else None
    for profile_name, profile_path in _iter_profile_dirs(ctx["service"]["base_dir"]):
        if clean_tmp:
            freed, removed = _clean_profile_tmp(profile_path)
            result_action = "tmp"
        else:
            freed, removed = _clean_profile_old_logs(profile_path, old_logs, now=now)
            result_action = f"old-logs-{old_logs}d"
        if not freed and not removed:
            continue
        results.append({
            "profile": profile_name,
            "action": result_action,
            "freed_bytes": freed,
            "freed_size": _format_bytes(freed),
            "removed_count": len(removed),
            "removed_paths": removed,
        })
    total = sum(item["freed_bytes"] for item in results)
    if json_flag:
        _write_json(ctx, _json_success("clean.profiles", f"Cleaned profiles ({_format_bytes(total)} freed)", cancelled=False, freed_bytes=total, freed_size=_format_bytes(total), profiles=results))
        return 0
    if not results:
        ctx["out"](f"{_dim('No matching profile cleanup candidates found.', ctx['use_color'])}\n")
        return 0
    for item in results:
        message = f"Cleaned {item['profile']} {item['action']} ({item['freed_size']} freed)"
        ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    ctx["out"](f"{_success(f'Total freed: {_format_bytes(total)}', ctx['use_color'])}\n")
    return 0

def handle_disk(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--candidates": {"key": "candidates", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, DISK_USAGE, positionals_key="targets", max_positionals=1)
    target = parsed["targets"][0] if parsed["targets"] else "home"
    if parsed["candidates"] and target != "profiles":
        raise CdxError(DISK_USAGE)
    if target == "home":
        path = ctx["service"]["base_dir"]
    elif target == "profiles":
        path = os.path.join(ctx["service"]["base_dir"], "profiles")
    else:
        raise CdxError(DISK_USAGE)
    stderr = ctx["options"].get("stderr", sys.stderr)
    show_progress = not parsed["json"] and hasattr(stderr, "isatty") and stderr.isatty()

    def progress(stage, name=None, index=None, total=None):
        if not show_progress:
            return
        if stage == "total":
            label = "CDX profiles" if target == "profiles" else "CDX home"
            ctx["err"](f"Measuring {label} disk usage...\n")
        elif stage == "profile":
            ctx["err"](f"Measuring profile {name} ({index}/{total})...\n")
        elif stage == "candidates":
            ctx["err"](f"Scanning cleanup candidates in {name} ({index}/{total})...\n")

    progress("total")
    bytes_used = _directory_size_bytes(path, runner=ctx["options"].get("diskUsageRunner"))
    payload = {
        "target": target,
        "path": path,
        "bytes": bytes_used,
        "size": _format_bytes(bytes_used),
    }
    if target == "profiles":
        payload["children"] = _directory_child_sizes(path, runner=ctx["options"].get("diskUsageRunner"), progress=progress)
    if parsed["candidates"]:
        candidates = _collect_profile_cleanup_candidates(
            ctx["service"]["base_dir"],
            runner=ctx["options"].get("diskUsageRunner"),
            now=ctx["options"].get("now")() if callable(ctx["options"].get("now")) else None,
            progress=progress,
        )
        payload["candidates"] = candidates
        payload["reclaimable_bytes"] = sum(item["bytes"] for item in candidates)
        payload["reclaimable_size"] = _format_bytes(payload["reclaimable_bytes"])
    if parsed["json"]:
        label = "CDX profiles" if target == "profiles" else "CDX home"
        _write_json(ctx, _json_success("disk", f"Measured {label} disk usage: {payload['size']}", disk=payload))
        return 0
    ctx["out"](f"{_format_disk_report(payload, use_color=ctx['use_color'])}\n")
    return 0

def handle_clean(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    profile_flags = ("--tmp", "--old-logs")
    has_profile_flag = any(arg in profile_flags or arg.startswith("--old-logs=") for arg in args)
    if args[:1] == ["profiles"] or has_profile_flag:
        if args[:1] == ["profiles"]:
            return _handle_clean_profiles(args[1:], ctx, json_flag)
        return _handle_clean_profiles(args, ctx, json_flag)
    yes = "--yes" in args
    args = [arg for arg in args if arg != "--yes"]
    service = ctx["service"]
    if len(args) == 0:
        targets = service["list_sessions"]()
    elif len(args) == 1:
        session = service["get_session"](args[0])
        if not session:
            raise CdxError(f"Unknown session: {args[0]}")
        targets = [session]
    else:
        raise CdxError("Usage: cdx clean [name] [--yes] [--json]")

    if not yes:
        target = targets[0]["name"] if len(targets) == 1 else f"all {len(targets)} sessions"
        confirm_fn = ctx["options"].get("confirmClean")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, target)
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Log cleanup requires an interactive terminal or --yes in non-interactive mode.")
        else:
            confirmed = _confirm_log_cleanup(target)
        if not confirmed:
            if json_flag:
                _write_json(ctx, _json_success("clean", "Cancelled.", cancelled=True, sessions=[]))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0

    cleaned_sessions = []
    for session in targets:
        log_paths = _list_launch_transcript_paths(session)
        if not log_paths:
            message = f"{session['name']}: no log found"
            cleaned_sessions.append({
                "session_name": session["name"],
                "cleared": False,
                "files_cleared": 0,
                "freed_kb": 0,
                "message": message,
            })
            if json_flag:
                continue
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
            continue
        total_size = 0
        cleared = 0
        for log_path in log_paths:
            try:
                total_size += os.path.getsize(log_path)
                open(log_path, "w").close()
                cleared += 1
            except OSError:
                continue
        if cleared:
            message = (
                f"Cleared {session['name']} logs ({cleared} file"
                f"{'' if cleared == 1 else 's'}, {round(total_size / 1024)} KB freed)"
            )
            cleaned_sessions.append({
                "session_name": session["name"],
                "cleared": True,
                "files_cleared": cleared,
                "freed_kb": round(total_size / 1024),
                "message": message,
            })
            if json_flag:
                continue
            ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        else:
            message = f"{session['name']}: no log found"
            cleaned_sessions.append({
                "session_name": session["name"],
                "cleared": False,
                "files_cleared": 0,
                "freed_kb": 0,
                "message": message,
            })
            if json_flag:
                continue
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    if json_flag:
        _write_json(ctx, _json_success("clean", "Cleaned session logs", cancelled=False, sessions=cleaned_sessions))
    return 0

def handle_doctor(rest, ctx):
    parsed = _parse_doctor_args(rest)
    report = collect_health_report(
        ctx["service"],
        ctx["service"]["base_dir"],
        env=ctx.get("env"),
        spawn_sync=ctx.get("spawn_sync"),
        check_provider_flags=parsed["check_provider_flags"],
    )
    report = filter_health_report(report, parsed["severity"])
    if parsed["json"]:
        _write_json(ctx, _json_success("doctor", "Collected health report", report=report))
    else:
        ctx["out"](f"{format_health_report(report, use_color=ctx['use_color'])}\n")
    return 0

def handle_repair(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--dry-run": {"key": "dry_run", "type": "bool", "default": False},
        "--force": {"key": "force", "type": "bool", "default": False},
    }, REPAIR_USAGE)
    dry_run = parsed["dry_run"] or not parsed["force"]
    report = repair_health(
        ctx["service"],
        ctx["service"]["base_dir"],
        env=ctx.get("env"),
        dry_run=dry_run,
        force=parsed["force"],
    )
    if parsed["json"]:
        _write_json(ctx, _json_success("repair", "Collected repair report", report=report))
    else:
        ctx["out"](f"{format_repair_report(report, use_color=ctx['use_color'])}\n")
        if dry_run:
            ctx["out"](f"{_dim('Tip: run cdx repair --force to apply safe repairs.', ctx['use_color'])}\n")
    return 0

def handle_update(rest, ctx):
    parsed = _parse_update_args(rest)
    if parsed["all"]:
        plan = collect_update_all_plan(ctx["service"], env=ctx.get("env"), runner=ctx["options"].get("runUpdateAll"))
        if not parsed["yes"]:
            if parsed["json"]:
                _write_json(ctx, _json_success("update.all", "Collected workstation update plan", plan=plan, apply_required=bool(plan["steps"])))
                return 0
            ctx["out"](f"{_format_update_all(plan, ctx['use_color'])}\n")
            if not plan["steps"]:
                return 0
            if not ctx["stdin_is_tty"]:
                raise CdxError("cdx update all requires an interactive terminal or --yes.")
            if input("Apply this plan? [y/N] ").strip().lower() not in ("y", "yes"):
                ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
                return 0
        def progress(event):
            if parsed["json"]:
                return
            step_name = event["step"]["name"]
            if event["phase"] == "start":
                progress_label = _info(f"[{event['index']}/{event['total']}]", ctx["use_color"])
                ctx["out"](f"{progress_label} {step_name}...\n")
            else:
                ctx["out"](f"  {_format_update_all_result(event['result'], ctx['use_color'])}\n")

        results = apply_update_all_plan(plan, ctx["service"], env=ctx.get("env"), runner=ctx["options"].get("runUpdateAll"), progress=progress)
        failed = [row for row in results if row.get("returncode") != 0]
        message = "Applied workstation update plan" if not failed else "Workstation update plan completed with failures"
        if parsed["json"]:
            _write_json(ctx, _json_success("update.all", message, plan=plan, results=results, failed=len(failed)))
        else:
            ctx["out"](f"{_success(message, ctx['use_color']) if not failed else _warn(message, ctx['use_color'])}\n")
        return 1 if failed else 0
    json_flag = parsed["json"]
    current_version = str(ctx.get("version") or "").strip()
    release_fetcher = ctx["options"].get("fetchLatestRelease") or fetch_latest_release
    target_version = None
    release_url = None
    update_available = False

    if parsed["version"] is not None:
        target_version = str(parsed["version"]).strip().lstrip("v")
    else:
        try:
            latest = (
                release_fetcher()
                if ctx["options"].get("fetchLatestRelease")
                else fetch_latest_release_or_raise(env=ctx.get("env"))
            )
        except LatestReleaseCheckError as error:
            raise CdxError(str(error)) from error
        if not latest:
            raise CdxError("Unable to check for the latest cdx-manager release. Check your network and try again.")
        target_version = str(latest.get("latest_version") or "").strip()
        release_url = latest.get("url")
        if not target_version:
            raise CdxError("Unable to determine the latest cdx-manager release.")
        update_available = is_newer_version(current_version, target_version)
        if parsed["check"] or not update_available:
            message = (
                f"Update available: cdx-manager {target_version} (current {current_version})"
                if update_available
                else f"cdx-manager {current_version} is already up to date."
            )
            if json_flag:
                _write_json(ctx, _json_success(
                    "update",
                    message,
                    checked=True,
                    update_available=update_available,
                    current_version=current_version,
                    target_version=target_version,
                    release_url=release_url,
                    warnings=[{
                        "code": "update_available",
                        "message": message,
                        "latest_version": target_version,
                        "url": release_url,
                    }] if update_available else [],
                ))
                return 0
            ctx["out"](f"{_warn(message, ctx['use_color']) if update_available else _success(message, ctx['use_color'])}\n")
            return 0

    if not parsed["yes"]:
        if not ctx["stdin_is_tty"]:
            raise CdxError("Update requires an interactive terminal or --yes in non-interactive mode.")
        answer = input(f"Update cdx-manager to {target_version}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            message = "Cancelled."
            if json_flag:
                _write_json(ctx, _json_success("update", message, cancelled=True, current_version=current_version, target_version=target_version))
                return 0
            ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
            return 0

    plan = build_update_plan(
        target_version=target_version,
        package_root=ctx["options"].get("packageRoot"),
        prefix=ctx["options"].get("prefix"),
        base_prefix=ctx["options"].get("basePrefix"),
    )
    results = run_update_plan(plan, runner=ctx["options"].get("runUpdate"), env=ctx.get("env"))
    failed = any((result.get("returncode") != 0) for result in results)
    if failed:
        raise CdxError(format_update_failure(results))

    warnings = []
    version_warning = verify_updated_command(
        target_version,
        runner=ctx["options"].get("runVersionCheck"),
        env=ctx.get("env"),
    )
    if version_warning:
        warnings.append(version_warning)

    message = f"Updated cdx-manager to {target_version}"
    if json_flag:
        _write_json(ctx, _json_success(
            "update",
            message,
            warnings=warnings,
            updated=True,
            current_version=current_version,
            target_version=target_version,
            mode=plan["mode"],
            steps=results,
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    for warning in warnings:
        ctx["out"](f"{_warn(warning['message'], ctx['use_color'])}\n")
    return 0
