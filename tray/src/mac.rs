//! The macOS run loop.
//!
//! `tray-icon` needs a live `NSApplication`, and every tray mutation has to
//! happen on the main thread. Rather than `app.run()`, which never returns and
//! would leave no place to poll from, this pumps the event queue itself with a
//! short timeout. One loop, on the main thread, doing three things in order:
//! drain menu clicks, refresh when the schedule says so, redraw.

use std::time::{Duration, Instant};

use objc2::rc::autoreleasepool;
use objc2::MainThreadMarker;
use objc2_app_kit::{NSApplication, NSApplicationActivationPolicy, NSEventMask};
use objc2_foundation::{NSDate, NSDefaultRunLoopMode};

use crate::backend;
use crate::events::set_alerts;
use crate::hint;
use crate::menu::ActionId;
use crate::runner::{announce, Render};
use crate::snapshot::Transport;
use crate::spool;

/// How long the pump blocks before looking at the clock again. Short enough
/// that Quit feels instant, long enough that an idle companion is not a
/// spinning loop.
const PUMP: Duration = Duration::from_millis(200);

pub fn run(transport: Transport) -> Result<(), String> {
    let mtm = MainThreadMarker::new().ok_or("the tray must start on the main thread")?;
    let app = NSApplication::sharedApplication(mtm);
    // Accessory: a menu bar item, no Dock tile, no app switcher entry. The same
    // intent as LSUIElement in the bundle, set here too so a bare binary run
    // from a terminal behaves the same way.
    app.setActivationPolicy(NSApplicationActivationPolicy::Accessory);

    let mut state = Render::first(&transport);
    let (tray, mut actions) = backend::build_tray(
        &state.icon_state,
        &state.tooltip,
        &state.entries,
        &state.rows,
    )?;
    // The first draw happens before the loop, so the alerts it showed have to
    // be acknowledged here too. Leaving it to the redraw block would hold them
    // unacknowledged for a whole poll period, and a companion quit inside that
    // window would have shown an alert CDX still considers undelivered.
    let mut spool = spool::Spool::idle();
    spool.watch(state.spool_path.as_deref(), transport.is_wsl());
    let mut alert_hint = hint::advance(None, state.fresh.len(), Instant::now());
    backend::set_title(&tray, hint::title(alert_hint, Instant::now()));
    announce(&transport, &state);
    let mut due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);

    loop {
        autoreleasepool(|_| {
            let until = NSDate::dateWithTimeIntervalSinceNow(PUMP.as_secs_f64());
            while let Some(event) = unsafe {
                app.nextEventMatchingMask_untilDate_inMode_dequeue(
                    NSEventMask::Any,
                    Some(&until),
                    NSDefaultRunLoopMode,
                    true,
                )
            } {
                app.sendEvent(&event);
            }
        });

        let mut redraw = false;
        while let Ok(event) = muda::MenuEvent::receiver().try_recv() {
            match actions.get(&event.id) {
                Some(ActionId::Quit) => return Ok(()),
                Some(ActionId::Refresh) => {
                    state = Render::next(&transport, state.tick, &state.history);
                    redraw = true;
                }
                Some(ActionId::OpenTerminal) => open_terminal("cdx status"),
                Some(ActionId::ToggleAlerts) => {
                    // Written through cdx rather than by the companion: the
                    // hook is what obeys the mute, and it reads CDX's store.
                    // The next poll brings the new state back, so the tick
                    // reflects what was actually recorded rather than what was
                    // clicked.
                    set_alerts(&transport, !state.alerts_enabled);
                    state = Render::next(&transport, state.tick, &state.history);
                    redraw = true;
                }
                Some(ActionId::Session(name)) => open_terminal(&format!("cdx {name}")),
                None => {}
            }
        }

        // An alert lands in the spool the moment a hook writes it. Polling for
        // it would cost up to a full period of latency on the one event the
        // user is actually waiting for, so a change pulls the next poll forward
        // instead.
        if spool.changed() {
            due = Instant::now();
        }
        if Instant::now() >= due {
            state = Render::next(&transport, state.tick, &state.history);
            redraw = true;
        }

        if redraw {
            actions = backend::update_tray(
                &tray,
                &state.icon_state,
                &state.tooltip,
                hint::title(alert_hint, Instant::now()),
                &state.entries,
                &state.rows,
            )?;
            // No enabled session means no reason to ask again. Wake up rarely
            // rather than never, so enabling one later is eventually noticed.
            due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);
            // Acknowledged only after the alert has been drawn. A companion
            // that dies in between is handed it again next poll and shows it
            // twice at worst; acknowledging first would lose it outright.
            spool.watch(state.spool_path.as_deref(), transport.is_wsl());
            alert_hint = hint::advance(alert_hint, state.fresh.len(), Instant::now());
            announce(&transport, &state);
        }
        let _ = &tray;
    }
}

/// Open Terminal on `cdx status`, the command this menu is a summary of.
///
/// Best effort by design: the tray never blocks on it, never waits for it, and
/// never reports its failure as a quota problem. A user whose terminal does not
/// open still has every figure in the menu they just clicked from.
/// Open Terminal on a command.
///
/// The command is built from a session name CDX itself produced, but it is
/// still quoted for AppleScript: a name is user-supplied text, and one
/// containing a quotation mark would otherwise end the string and turn the rest
/// into script.
fn open_terminal(command: &str) {
    let escaped = command.replace('\\', "\\\\").replace('"', "\\\"");
    let _ = std::process::Command::new("osascript")
        .args([
            "-e",
            &format!(r#"tell application "Terminal" to do script "{escaped}""#),
            "-e",
            r#"tell application "Terminal" to activate"#,
        ])
        .spawn();
}
