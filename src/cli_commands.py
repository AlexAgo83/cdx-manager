#!/usr/bin/env python3
"""Facade over the per-domain command modules in src/commands/.

Every `handle_*` entry point now lives in one of the nine domain modules; this
module defines nothing and only re-exports them, so `from .cli_commands import
handle_x` keeps resolving for src/cli.py and the tests. Add a new command to
its domain module and re-export it here.

The `# noqa: F401` markers are load-bearing: without them ruff removes the
re-exports as unused, and callers importing through this facade break.
`test_cli_commands_facade_still_exposes_every_name_its_callers_import` guards
that contract.
"""
from .cli_args import STATUS_USAGE  # noqa: F401  (re-exported for cli.py)
from .cli_helpers import (  # noqa: F401  (several names are re-exported for cli.py / tests)
    API_SCHEMA_VERSION,
    _bootstrap_claude_setup_token,
    _build_handoff_context,
    _extract_claude_oauth_token,
    _format_bytes,
    _format_launch_config,
    _format_launch_setting_value,
    _format_launch_settings_hint,
    _handoff_launch_prompt,
    _json_failure,
    _json_success,
    _latest_handoff_transcript_path,
    _local_now_iso,
    _make_notify_progress,
    _make_status_progress,
    _read_handoff_transcript,
    _resolve_confirmation,
    _resume_capability_for_session,
    _update_notice_warnings,
    _warn_if_session_already_running,
    _write_claude_oauth_token,
    _write_json,
    _write_update_notice,
)
from .cli_view import handle_view as handle_view  # re-export for cli.py / tests
from .commands.auth import (  # re-export for cli.py / tests
    _confirm_reset as _confirm_reset,
)
from .commands.auth import (
    handle_login as handle_login,
)
from .commands.auth import (
    handle_logout as handle_logout,
)
from .commands.auth import (
    handle_notify as handle_notify,
)
from .commands.auth import (
    handle_reset as handle_reset,
)
from .commands.backup import (  # noqa: F401
    _resolve_bundle_passphrase,
    handle_export,
    handle_import,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.context_memory import (  # noqa: F401
    _list_memory_entries,
    _memory_payload,
    _memory_target,
    _parse_memory_args,
    handle_context,
    handle_memory,
)
from .commands.launch import (  # re-export for cli.py / tests
    _format_resume_capability as _format_resume_capability,
)
from .commands.launch import (
    handle_can_resume as handle_can_resume,
)
from .commands.launch import (
    handle_handoff as handle_handoff,
)
from .commands.launch import (
    handle_launch as handle_launch,
)
from .commands.launch import (
    handle_resume as handle_resume,
)
from .commands.lifecycle import (  # re-export for cli.py / tests
    _confirm_removal as _confirm_removal,
)
from .commands.lifecycle import (
    handle_add as handle_add,
)
from .commands.lifecycle import (
    handle_copy as handle_copy,
)
from .commands.lifecycle import (
    handle_disable as handle_disable,
)
from .commands.lifecycle import (
    handle_enable as handle_enable,
)
from .commands.lifecycle import (
    handle_label as handle_label,
)
from .commands.lifecycle import (
    handle_remove as handle_remove,
)
from .commands.lifecycle import (
    handle_rename as handle_rename,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.maintenance import (  # noqa: F401
    _candidate,
    _clean_profile_old_logs,
    _clean_profile_tmp,
    _collect_old_logs,
    _collect_profile_cleanup_candidates,
    _confirm_log_cleanup,
    _confirm_profile_cleanup,
    _directory_child_sizes,
    _directory_size_bytes,
    _format_cleanup_candidates,
    _format_disk_report,
    _format_update_all,
    _format_update_all_result,
    _handle_clean_profiles,
    _iter_profile_dirs,
    _parse_days,
    _remove_path,
    handle_clean,
    handle_disk,
    handle_doctor,
    handle_repair,
    handle_update,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.runs import (  # noqa: F401
    DETACHED_PROMPT_SUFFIX,
    DETACHED_RUN_ID_ENV,
    RUN_TAIL_READ_BYTES,
    _cdx_self_command,
    _consume_detached_prompt_file,
    _detached_child_argv,
    _detached_spawn_options,
    _run_registry,
    _select_headless_session,
    _selection_reason,
    _spawn_detached_run,
    _tail_file_lines,
    handle_run,
    handle_run_report,
    handle_run_status,
    handle_run_tail,
    handle_runs,
    handle_schema,
    handle_select,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.settings import (  # re-export for cli.py / tests
    _apply_launch_settings as _apply_launch_settings,
)
from .commands.settings import (
    _clear_launch_settings as _clear_launch_settings,
)
from .commands.settings import (
    _format_bulk_launch_summary as _format_bulk_launch_summary,
)
from .commands.settings import (
    _resolve_bulk_launch_targets as _resolve_bulk_launch_targets,
)
from .commands.settings import (
    handle_launch_setting_alias as handle_launch_setting_alias,
)
from .commands.settings import (
    handle_set as handle_set,
)
from .commands.settings import (
    handle_unset as handle_unset,
)
from .commands.status import (  # re-export for cli.py / tests
    _active_session_names as _active_session_names,
)
from .commands.status import (
    _format_duration_ms as _format_duration_ms,
)
from .commands.status import (
    _format_history as _format_history,
)
from .commands.status import (
    _format_history_period as _format_history_period,
)
from .commands.status import (
    _format_history_summary as _format_history_summary,
)
from .commands.status import (
    _format_launch_configs as _format_launch_configs,
)
from .commands.status import (
    _format_next_pct as _format_next_pct,
)
from .commands.status import (
    _format_next_selection as _format_next_selection,
)
from .commands.status import (
    _format_period_display as _format_period_display,
)
from .commands.status import (
    _format_refresh_warning as _format_refresh_warning,
)
from .commands.status import (
    _format_stats as _format_stats,
)
from .commands.status import (
    _format_token_count as _format_token_count,
)
from .commands.status import (
    _has_valid_local_claude_auth as _has_valid_local_claude_auth,
)
from .commands.status import (
    _is_invalid_claude_usage_auth as _is_invalid_claude_usage_auth,
)
from .commands.status import (
    _next_action as _next_action,
)
from .commands.status import (
    _refresh_claude_auth_states as _refresh_claude_auth_states,
)
from .commands.status import (
    _refresh_warning_payloads as _refresh_warning_payloads,
)
from .commands.status import (
    _resolve_last_launch_session as _resolve_last_launch_session,
)
from .commands.status import (
    _rows_by_session as _rows_by_session,
)
from .commands.status import (
    _stats_totals as _stats_totals,
)
from .commands.status import (
    _summarize_history as _summarize_history,
)
from .commands.status import (
    _summarize_stats as _summarize_stats,
)
from .commands.status import (
    _token_value as _token_value,
)
from .commands.status import (
    _write_refresh_warnings as _write_refresh_warnings,
)
from .commands.status import (
    handle_config as handle_config,
)
from .commands.status import (
    handle_configs as handle_configs,
)
from .commands.status import (
    handle_history as handle_history,
)
from .commands.status import (
    handle_last as handle_last,
)
from .commands.status import (
    handle_next as handle_next,
)
from .commands.status import (
    handle_stats as handle_stats,
)
from .commands.status import (
    handle_status as handle_status,
)


