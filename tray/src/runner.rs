//! What one poll produced: what to draw, and when to poll again.
//!
//! Shared by every platform loop. The loops differ only in how they pump their
//! event queue; what they show and when they ask again is decided here, so the
//! macOS and Windows companions cannot drift apart in behaviour.

use std::time::Duration;

use crate::events::{self, Event};
use crate::menu;
use crate::schedule::Tick;
use crate::snapshot::{fetch, Transport};
use crate::unread::Unread;

/// One session as a drawn row needs it: where it sits in the menu, and the
/// values a cell shows. Computed here rather than in a backend so the platform
/// that can draw and the two that cannot start from the same data.
/// Read only where a platform can draw a cell, which today is macOS alone.
/// Kept platform-neutral anyway: the data is the same everywhere, and gating
/// the struct would make every caller match on the target.
#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct Row {
    pub menu_index: usize,
    pub name: String,
    /// Carried so the drawn row can say what the text row says. A cell replaces
    /// the label entirely, so a provider missing here is a provider the macOS
    /// user cannot see at all.
    pub provider: String,
    pub percent: Option<f64>,
    pub state: String,
    pub figure: String,
}

pub struct Render {
    pub icon_state: String,
    pub tooltip: String,
    pub entries: Vec<menu::Entry>,
    /// `None` when there is no enabled session and nothing to ask about.
    pub delay: Option<Duration>,
    pub tick: Tick,
    /// Alerts collected this poll, already acknowledged. The backend raises a
    /// notification for each of these once; what stays in the menu is whatever
    /// is still unread.
    pub fresh: Vec<Event>,
    /// The session rows, paired with their position in `entries`. Consumed
    /// only by a platform that can draw a cell — macOS today — but computed
    /// once here so the three backends never disagree about what a row says.
    #[allow(dead_code)]
    pub rows: Vec<Row>,
    /// Where the spool lives, so the loop can notice an alert between polls.
    pub spool_path: Option<String>,
    /// Whether alerts may raise a banner, so the switch draws its real state.
    pub alerts_enabled: bool,
}

impl Render {
    /// How long to wait when there is nothing to poll for. Rarely rather than
    /// never, so enabling a session later is eventually noticed without the
    /// user having to restart the companion.
    pub const IDLE_WAKEUP: Duration = Duration::from_secs(3600);

    pub fn first(transport: &Transport, unread: &mut Unread) -> Self {
        Self::next(transport, Tick::start(), unread)
    }

    /// One poll: say we are alive, collect what CDX held for us, then draw.
    ///
    /// The heartbeat goes first. It is what tells `cdx notify` a tray owns the
    /// alerts, so a companion that has not beaten yet must not be handed one it
    /// could then fail to collect — CDX delivering it directly is the safe way
    /// round, and the only cost is one poll of latency at startup.
    /// `unread` is taken by reference and mutated: this poll's alerts join it,
    /// and the menu built here is what a later consultation counts as read.
    pub fn next(transport: &Transport, tick: Tick, unread: &mut Unread) -> Self {
        match fetch(transport) {
            Ok(snap) => {
                let tick = tick.succeeded(snap.session_count);
                // The poll that wrote the heartbeat also carried the alerts, so
                // one crossing does the whole job.
                let fresh = snap.events.clone();
                unread.record(&fresh);
                let entries_for_rows = menu::build_with_alerts(&snap, unread.items());
                // What this menu shows is what the next opening will count as
                // read. Captured at the draw because the draw is the only place
                // that knows what went into the menu.
                unread.mark_drawn();
                Render {
                    icon_state: snap.icon_state.clone(),
                    tooltip: snap.tooltip.clone(),
                    rows: rows_for(&entries_for_rows, &snap.sessions),
                    spool_path: snap.spool_path.clone(),
                    alerts_enabled: snap.alerts_enabled,
                    entries: entries_for_rows.clone(),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                    fresh,
                }
            }
            Err(reason) => {
                let tick = tick.failed();
                // Nothing was collected, so nothing is acknowledged and what was
                // unread stays unread.
                let fresh = Vec::new();
                Render {
                    // Unavailable is a state, not a crash. The icon stays, and
                    // it shows that nothing is known rather than a stale figure.
                    icon_state: "unknown".to_string(),
                    tooltip: format!("CDX · unavailable · {reason}"),
                    // Nothing to watch while CDX is unreachable; the next
                    // successful poll says where the spool is again.
                    spool_path: None,
                    // Unknown reads as on: a CDX we cannot reach must not look
                    // like a mute nobody set.
                    alerts_enabled: true,
                    rows: Vec::new(),
                    entries: menu::build_unavailable(&reason),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                    fresh,
                }
            }
        }
    }
}

/// The ids drawn this poll, ready to acknowledge.
fn fresh_ids(state: &Render) -> Vec<String> {
    state.fresh.iter().map(|event| event.id.clone()).collect()
}

/// Raise a notification for each alert drawn this poll, then acknowledge them.
///
/// Delivery comes first and acknowledgement second, so a companion that dies in
/// between shows an alert twice rather than losing it. The event id is reused
/// as the notification identifier: macOS then replaces rather than stacks if
/// the same alert is ever delivered again.
pub fn announce(transport: &Transport, state: &Render) {
    for event in &state.fresh {
        crate::notify::deliver(&event.title, &event.message, &event.id);
    }
    events::acknowledge(transport, &fresh_ids(state));
}

/// Pair each session with the menu position its row occupies.
///
/// The menu carries a summary line and separators, so a session's rank is not
/// its menu index. Reading the positions back from the entries keeps the two in
/// step without the menu builder having to report them, and resolving by the
/// name the submenu is about means a cell can only ever be drawn onto the row
/// that carries that name.
fn rows_for(entries: &[menu::Entry], sessions: &[crate::snapshot::Session]) -> Vec<Row> {
    let mut rows = Vec::new();
    for (menu_index, entry) in entries.iter().enumerate() {
        if let menu::Entry::Submenu {
            about: menu::ActionId::Session(name),
            ..
        } = entry
        {
            if let Some(session) = sessions.iter().find(|s| s.name == *name) {
                rows.push(Row {
                    menu_index,
                    name: session.name.clone(),
                    provider: session.provider.clone(),
                    percent: session.available_pct,
                    // Same thresholds the icon uses, so a red bar and a red
                    // glyph can never disagree about the same session.
                    state: menu::state_for(session.available_pct).to_string(),
                    figure: menu::pct(session.available_pct),
                });
            }
        }
    }
    rows
}
