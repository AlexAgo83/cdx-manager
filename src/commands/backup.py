"""Backup domain commands: export, import.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import getpass
import sys

from ..backup_bundle import read_bundle_meta
from ..cli_args import _parse_export_args, _parse_import_args
from ..cli_helpers import _format_export_report, _json_success, _make_export_progress, _write_json
from ..cli_render import _success
from ..errors import CdxError


def _resolve_bundle_passphrase(ctx, env_var, prompt, confirm=False, use_stdin=False):
    env = ctx.get("env", {})
    if env_var:
        passphrase = env.get(env_var)
        if not passphrase:
            raise CdxError(f"Environment variable {env_var} is empty or unset.")
        return passphrase
    if use_stdin:
        reader = ctx["options"].get("read_stdin")
        raw = reader() if callable(reader) else sys.stdin.readline()
        passphrase = (raw or "").rstrip("\r\n")
        if not passphrase:
            raise CdxError("Bundle passphrase from stdin is empty.")
        return passphrase
    if not ctx["stdin_is_tty"]:
        raise CdxError("Encrypted bundle export/import requires an interactive terminal, --passphrase-env, or --passphrase-stdin.")
    getpass_fn = ctx["options"].get("getpass") or getpass.getpass
    passphrase = getpass_fn(prompt)
    if not passphrase:
        raise CdxError("Bundle passphrase cannot be empty.")
    if confirm:
        confirmation = getpass_fn("Confirm bundle passphrase: ")
        if passphrase != confirmation:
            raise CdxError("Bundle passphrase confirmation does not match.")
    return passphrase

def handle_export(rest, ctx):
    parsed = _parse_export_args(rest)
    passphrase = None
    if parsed["include_auth"]:
        passphrase = _resolve_bundle_passphrase(
            ctx,
            parsed["passphrase_env"],
            "Bundle passphrase: ",
            confirm=True,
            use_stdin=parsed["passphrase_stdin"],
        )
    result = ctx["service"]["export_bundle"](
        parsed["file_path"],
        include_auth=parsed["include_auth"],
        session_names=parsed["session_names"],
        passphrase=passphrase,
        force=parsed["force"],
        progress_callback=None if parsed["json"] else _make_export_progress(ctx),
    )
    session_count = len(result["session_names"])
    auth_suffix = " with auth" if result["include_auth"] else ""
    message = f"Exported {session_count} session{'s' if session_count != 1 else ''}{auth_suffix} to {result['path']}"
    payload = _json_success(
        "export",
        message,
        bundle=result,
    )
    if parsed["json"]:
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    ctx["out"](f"{_format_export_report(result)}\n")
    return 0

def handle_import(rest, ctx):
    parsed = _parse_import_args(rest)
    passphrase = None
    try:
        with open(parsed["file_path"], "rb") as handle:
            meta = read_bundle_meta(handle.read())
    except OSError as error:
        raise CdxError(f"Bundle file not found: {parsed['file_path']}") from error
    if meta.get("encrypted"):
        passphrase = _resolve_bundle_passphrase(
            ctx,
            parsed["passphrase_env"],
            "Bundle passphrase: ",
            confirm=False,
            use_stdin=parsed["passphrase_stdin"],
        )
    result = ctx["service"]["import_bundle"](
        parsed["file_path"],
        passphrase=passphrase,
        session_names=parsed["session_names"],
        force=parsed["force"],
        merge=parsed["merge"],
        allow_authless_force=parsed["allow_authless_force"],
    )
    session_count = len(result["session_names"])
    auth_suffix = " with auth" if result["include_auth"] else ""
    message = f"Imported {session_count} session{'s' if session_count != 1 else ''}{auth_suffix} from {result['path']}"
    payload = _json_success(
        "import",
        message,
        bundle=result,
    )
    if parsed["json"]:
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0
