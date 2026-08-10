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
use crate::menu::{self, ActionId};
use crate::schedule::Tick;
use crate::snapshot::{fetch, Transport};

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

    let mut state = Render::first(&transport)?;
    let (mut tray, mut actions) = backend::build_tray(&state.icon_state, &state.entries)?;
    let mut due = Instant::now() + state.delay.unwrap_or(Duration::from_secs(3600));

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
                    state = Render::next(&transport, state.tick);
                    redraw = true;
                }
                Some(ActionId::OpenTerminal) => open_terminal(),
                None => {}
            }
        }

        if Instant::now() >= due {
            state = Render::next(&transport, state.tick);
            redraw = true;
        }

        if redraw {
            let (next_tray, next_actions) = backend::build_tray(&state.icon_state, &state.entries)?;
            tray = next_tray;
            actions = next_actions;
            // No enabled session means no reason to ask again. Wake up rarely
            // rather than never, so enabling one later is eventually noticed.
            due = Instant::now() + state.delay.unwrap_or(Duration::from_secs(3600));
        }
        let _ = &tray;
    }
}

/// Everything one poll produced: what to draw, and when to poll again.
struct Render {
    icon_state: String,
    entries: Vec<menu::Entry>,
    delay: Option<Duration>,
    tick: Tick,
}

impl Render {
    fn first(transport: &Transport) -> Result<Self, String> {
        Ok(Self::next(transport, Tick::start()))
    }

    fn next(transport: &Transport, tick: Tick) -> Self {
        match fetch(transport) {
            Ok(snap) => {
                let tick = tick.succeeded(snap.session_count);
                Render {
                    icon_state: snap.icon_state.clone(),
                    entries: menu::build(&snap),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                }
            }
            Err(reason) => {
                let tick = tick.failed();
                Render {
                    // Unavailable is a state, not a crash. The icon stays, and
                    // it shows that nothing is known rather than a stale figure.
                    icon_state: "unknown".to_string(),
                    entries: menu::build_unavailable(&reason),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                }
            }
        }
    }
}

/// Open the user's terminal on `cdx status`. Best effort: the tray never blocks
/// on it and never reports its failure as a quota problem.
fn open_terminal() {
    let _ = std::process::Command::new("open")
        .args(["-a", "Terminal", "/usr/bin/env"])
        .spawn();
}
