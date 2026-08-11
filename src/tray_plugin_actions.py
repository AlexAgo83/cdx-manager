"""What a card action is allowed to do.

The tray sends back an action id, never a command, and this is the only place
that turns one into behaviour. Everything an integration can cause the machine
to do is written here, in full, as a fixed vocabulary: refresh a card, open the
Logics viewer, or open it focused on one document.

The consequence worth stating: an adapter cannot extend this by producing a
different id. An id CDX does not recognise is refused, and refusal is the
default branch rather than the exception — so an integration gaining a new
capability is a change to this file, reviewed like any other.
"""
from .errors import CdxError

ACTION_UNKNOWN = "tray_plugin_action_unknown"


def perform_action(action, ctx):
    """Run one action id. Never raises for a bad id: it reports."""
    if not isinstance(action, str) or "." not in action:
        return _unknown(action)
    plugin, rest = action.split(".", 1)
    verb, _, reference = rest.partition(":")
    if plugin != "logics":
        return _unknown(action)
    if verb == "refresh":
        # The card is rebuilt by the next `cdx tray status --refresh`, which the
        # tray issues itself. Nothing to do here beyond saying so, and saying so
        # is what keeps the action id meaningful rather than silently ignored.
        return {"ok": True, "code": None, "message": "The Logics card refreshes on the next tray refresh."}
    if verb == "open":
        return _open_viewer(ctx, None)
    if verb == "focus" and reference:
        return _open_viewer(ctx, reference)
    return _unknown(action)


def _open_viewer(ctx, reference):
    from .logics_view import missing_logics_manager_failure, resolve_logics_manager, run_logics_viewer

    executable = resolve_logics_manager(ctx.get("env") or {})
    if not executable:
        failure = missing_logics_manager_failure()
        return {"ok": False, "code": failure["code"], "message": failure["message"]}
    extra = ["--focus", reference] if reference else []
    try:
        run_logics_viewer(
            executable, ctx.get("cwd"), env=ctx.get("env"),
            extra_args=extra, runner=ctx.get("spawn_detached_runner"),
        )
    except (OSError, CdxError) as error:
        return {"ok": False, "code": "logics_viewer_failed", "message": str(error)}
    where = f" focused on {reference}" if reference else ""
    return {"ok": True, "code": None, "message": f"Opened the Logics viewer{where}."}


def _unknown(action):
    return {
        "ok": False,
        "code": ACTION_UNKNOWN,
        "message": f"CDX does not know the tray action {action!r}.",
    }
