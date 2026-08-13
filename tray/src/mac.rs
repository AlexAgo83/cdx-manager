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
use crate::events::{run_plugin_action, set_alerts, set_terminal};
use crate::mac_menu_open;
use crate::menu::ActionId;
use crate::runner::{announce, Render};
use crate::snapshot::Transport;
use crate::spool;
use crate::unread::Unread;

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

    let mut unread = Unread::new();
    let mut state = Render::first(&transport, &mut unread);
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
    let mut observing = mac_menu_open::installed();
    backend::set_title(&tray, unread.marker());
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

        // CDX asks for the process, not for the files: an update replaces the
        // binary underneath a companion that would otherwise keep running the
        // old one. Checked before anything else in the iteration so a stop is
        // never delayed by work about to be thrown away.
        if crate::instance::stop_requested() {
            return Ok(());
        }

        let mut redraw = false;
        // The menu the user opened is the one drawn at the last redraw, so what
        // it showed is what has been read. Anything that arrived since is not
        // in that set and stays unread.
        let was_opened = mac_menu_open::opened();
        if was_opened || !observing {
            mac_menu_open::trace(&format!(
                "loop: observing={observing} opened={was_opened} unread={}",
                unread.marker().unwrap_or_else(|| "none".into())
            ));
        }
        if observing && was_opened && unread.consulted() {
            // Rebuild from the same poll, so the list and the badge
            // stop saying different things the moment one changes.
            state.redrawn(&mut unread);
            redraw = true;
        }
        while let Ok(event) = muda::MenuEvent::receiver().try_recv() {
            match actions.get(&event.id) {
                Some(ActionId::Quit) => return Ok(()),
                Some(ActionId::Refresh) => {
                    state = Render::next(&transport, state.tick, &mut unread);
                    redraw = true;
                }
                Some(ActionId::OpenTerminal) => {
                    open_terminal_in("cdx status", state.terminal.as_deref())
                }
                Some(ActionId::ToggleAlerts) => {
                    // Written through cdx rather than by the companion: the
                    // hook is what obeys the mute, and it reads CDX's store.
                    // The next poll brings the new state back, so the tick
                    // reflects what was actually recorded rather than what was
                    // clicked.
                    set_alerts(&transport, !state.alerts_enabled);
                    state = Render::next(&transport, state.tick, &mut unread);
                    redraw = true;
                }
                Some(ActionId::SetTerminal(name)) => {
                    set_terminal(&transport, name);
                    state = Render::next(&transport, state.tick, &mut unread);
                    redraw = true;
                }
                Some(ActionId::Session(name)) => {
                    open_terminal_in(&format!("cdx {name}"), state.terminal.as_deref())
                }
                // A view, not an edit: `cdx config` prints the settings that
                // will apply to the next launch, and the tray never claims to
                // change an assistant already running.
                Some(ActionId::SessionConfig(name)) => {
                    open_terminal_in(&format!("cdx config {name}"), state.terminal.as_deref())
                }
                // Handed back exactly as it arrived. The companion knows no
                // card action and can compose none, so CDX decides what, if
                // anything, an id means.
                Some(ActionId::Plugin { action, root }) => {
                    run_plugin_action(&transport, action, root.as_deref())
                }
                Some(ActionId::AlertGroup) => {}
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
            state = Render::next(&transport, state.tick, &mut unread);
            redraw = true;
        }

        if redraw {
            actions = backend::update_tray(
                &tray,
                &state.icon_state,
                &state.tooltip,
                unread.marker(),
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
            // The menu was rebuilt, so the delegate has to be set on the new
            // one. A draw that could not install it stops the clearing rather
            // than clearing against a menu nobody is watching.
            observing = mac_menu_open::installed();
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
/// Open a command in the chosen terminal, or in Terminal.app.
///
/// The two paths are different mechanisms, not one with a variable in it.
/// Terminal.app is driven by AppleScript, which is what lets a command be typed
/// into an existing window. Every other terminal has its own scripting dialect
/// or none, so the portable move is the oldest one: write the command to a
/// script and ask the application to open it. `open -a` resolves an application
/// by name or bundle id and refuses anything that is not one, which is the
/// second half of why a preference cannot become a command.
fn open_terminal_in(command: &str, preferred: Option<&str>) {
    let Some(app) = preferred else {
        let escaped = command.replace('\\', "\\\\").replace('"', "\\\"");
        let _ = std::process::Command::new("osascript")
            .args([
                "-e",
                &format!(r#"tell application "Terminal" to do script "{escaped}""#),
                "-e",
                r#"tell application "Terminal" to activate"#,
            ])
            .spawn();
        return;
    };
    match script_for(command) {
        Some(path) => {
            let spawned = std::process::Command::new("open")
                .args(["-a", app, &path])
                .spawn();
            if spawned.is_err() {
                // A named terminal that is not installed must not leave the
                // click doing nothing.
                open_terminal_in(command, None);
            }
        }
        None => open_terminal_in(command, None),
    }
}

/// A one-shot script carrying the command, for a terminal that has no scripting
/// interface we can rely on.
///
/// The content is built here from CDX's own command, never from the preference:
/// the preference names the application that opens this file and nothing else.
/// It removes itself, so a menu clicked all day does not fill the temporary
/// directory with copies of the same line.
fn script_for(command: &str) -> Option<String> {
    use std::io::Write;
    use std::os::unix::fs::PermissionsExt;

    let path = std::env::temp_dir().join(format!("cdx-open-{}.sh", std::process::id()));
    let mut file = std::fs::File::create(&path).ok()?;
    writeln!(file, "#!/bin/sh")
        .and_then(|()| writeln!(file, "rm -f \"$0\""))
        .and_then(|()| writeln!(file, "{command}"))
        .ok()?;
    std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).ok()?;
    Some(path.to_string_lossy().into_owned())
}
