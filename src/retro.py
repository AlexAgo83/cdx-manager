"""Session retrospectives: what the user had to correct, so the next session knows it.

With `cdx set <name> --retro on`, the end of an interactive session starts a
detached, read-only `cdx run --kind retro` on a ready account. It reads the
session's transcript and reports the corrections the user made and the lessons
worth keeping, each with where it belongs (memory, runbook, skill, CLAUDE.md).
It changes nothing: `cdx retro` shows the reports, and the user decides.
"""

import json
import os
import shutil
import subprocess

#: A session with fewer prompts than this rarely holds a correction worth a model call.
MIN_USER_PROMPTS = 3

PROMPT = """You are writing a retrospective of one finished coding-agent session. Do not modify any file.

Transcript (JSONL, possibly large; read it in bounded portions, never all at once): {transcript}
Project folder: {cwd}

Find the moments where the user corrected, redirected or overruled the agent, and the
non-obvious facts the session had to discover. Ignore routine back-and-forth.

Answer in Markdown with exactly these sections:
## Corrections
One bullet per correction: what the agent did, what the user wanted, in one line each.
## Lessons
One bullet per lesson worth keeping for future sessions, each starting with where it belongs:
`memory:`, `runbook:`, `skill:` or `CLAUDE.md:`, followed by the exact text to add.
## Verdict
One line: "nothing to learn" if both sections are empty, else the single most useful lesson.
"""


def enabled(session):
    return (session.get("launch") or {}).get("retro") is True


def start(session, cwd, transcript, env=None, popen=subprocess.Popen):
    """Start the retro run in the background; returns the argv, or None when skipped."""
    env = {**os.environ, **(env or {})}
    if not enabled(session) or not transcript or not os.path.isfile(transcript):
        return None
    if env.get("CDX_RETRO") == "1" or _user_prompts(transcript) < MIN_USER_PROMPTS:
        return None
    executable = env.get("CDX_BIN") or shutil.which("cdx", path=env.get("PATH")) or "cdx"
    argv = [
        executable, "run", "--provider", session["provider"], "--cwd", cwd, "--kind", "retro",
        "--permission", "read-only", "--power", "low", "--detach", "--json",
        "--prompt", PROMPT.format(transcript=transcript, cwd=cwd),
    ]
    env["CDX_RETRO"] = "1"  # a retro never asks for a retro of itself
    try:
        popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None
    return argv


def _user_prompts(transcript):
    """Prompts the user typed: Claude `user` records that are not tool results, Codex `user_message` events.

    Size is no proxy: one long handoff prompt makes a large transcript of a session
    that never started.
    """
    count = 0
    try:
        with open(transcript, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if ('"type":"user"' in line and '"tool_result"' not in line) or '"type":"user_message"' in line:
                    count += 1
                    if count >= MIN_USER_PROMPTS:
                        break
    except OSError:
        return 0
    return count


def reports(registry, limit=5):
    """The newest retro runs, newest first, with their text when finished."""
    found = []
    for run in registry.list(limit=200):
        if run.get("kind") != "retro":
            continue
        payload = run.get("final_payload") if isinstance(run.get("final_payload"), dict) else {}
        found.append({"run_id": run.get("run_id"), "status": run.get("status"), "cwd": run.get("cwd"),
                      "started_at": run.get("started_at"), "session": run.get("session"),
                      "report": _result_text(payload.get("stdout_path"))})
        if len(found) >= limit:
            break
    return found


def _result_text(stdout_path):
    """The answer of a finished run: Claude's `result`, else where to read it."""
    if not stdout_path or not os.path.isfile(stdout_path):
        return None
    try:
        with open(stdout_path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return f"(see {stdout_path})"
    result = document.get("result") if isinstance(document, dict) else None
    return result if isinstance(result, str) else f"(see {stdout_path})"


def handle_retro(rest, ctx):
    from .cli_helpers import _json_success, _write_json
    from .errors import CdxError
    from .run_registry import RunRegistry

    json_flag = "--json" in rest
    args = [arg for arg in rest if arg != "--json"]
    limit = 5
    if args[:1] == ["--limit"] and len(args) == 2 and args[1].isdigit():
        limit = int(args[1])
    elif args:
        raise CdxError("Usage: cdx retro [--limit N] [--json]")
    found = reports(RunRegistry(ctx["service"]["base_dir"]), limit=limit)
    if json_flag:
        _write_json(ctx, _json_success("retro", f"{len(found)} retro(s)", retros=found))
        return 0
    if not found:
        ctx["out"]("No session retro yet. Turn them on with `cdx set <name> --retro on`.\n")
        return 0
    for item in found:
        ctx["out"](f"## {item['started_at']} · {item['cwd']} · {item['status']}\n{item['report'] or '(still running)'}\n\n")
    return 0
