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

/// One session as a drawn row needs it: where it sits in the menu, and the
/// three values a cell shows. Computed here rather than in a backend so the
/// platform that can draw and the two that cannot start from the same data.
/// Read only where a platform can draw a cell, which today is macOS alone.
/// (`session_names` covers the click, so the other backends need none of this.)
/// Kept platform-neutral anyway: the data is the same everywhere, and gating
/// the struct would make every caller match on the target.
#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct Row {
    pub menu_index: usize,
    pub name: String,
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
    /// Alerts collected this poll, already acknowledged. The backend shows
    /// these once; `history` is what stays in the menu.
    pub fresh: Vec<Event>,
    /// Recent alerts, oldest first, bounded.
    pub history: Vec<Event>,
    /// The session rows, paired with their position in `entries`. Consumed
    /// only by a platform that can draw a cell — macOS today — but computed
    /// once here so the three backends never disagree about what a row says.
    #[allow(dead_code)]
    pub rows: Vec<Row>,
    /// Where the spool lives, so the loop can notice an alert between polls.
    pub spool_path: Option<String>,
    /// Whether alerts may raise a banner, so the switch draws its real state.
    pub alerts_enabled: bool,
    /// Session names in menu order, so a clicked row resolves to the session it
    /// names. Kept beside the entries rather than inside them: the menu id has
    /// to stay `Copy`, and a name embedded in it could drift from the snapshot.
    pub session_names: Vec<String>,
}

impl Render {
    /// How long to wait when there is nothing to poll for. Rarely rather than
    /// never, so enabling a session later is eventually noticed without the
    /// user having to restart the companion.
    pub const IDLE_WAKEUP: Duration = Duration::from_secs(3600);

    pub fn first(transport: &Transport) -> Self {
        Self::next(transport, Tick::start(), &[])
    }

    /// One poll: say we are alive, collect what CDX held for us, then draw.
    ///
    /// The heartbeat goes first. It is what tells `cdx notify` a tray owns the
    /// alerts, so a companion that has not beaten yet must not be handed one it
    /// could then fail to collect — CDX delivering it directly is the safe way
    /// round, and the only cost is one poll of latency at startup.
    pub fn next(transport: &Transport, tick: Tick, previous: &[Event]) -> Self {
        match fetch(transport) {
            Ok(snap) => {
                let tick = tick.succeeded(snap.session_count);
                // The poll that wrote the heartbeat also carried the alerts, so
                // one crossing does the whole job.
                let fresh = snap.events.clone();
                let history = merge_history(previous, &fresh);
                let entries_for_rows = menu::build_with_alerts(&snap, &history);
                Render {
                    icon_state: snap.icon_state.clone(),
                    tooltip: snap.tooltip.clone(),
                    rows: rows_for(&entries_for_rows, &snap.sessions),
                    spool_path: snap.spool_path.clone(),
                    alerts_enabled: snap.alerts_enabled,
                    session_names: snap.sessions.iter().map(|s| s.name.clone()).collect(),
                    entries: entries_for_rows.clone(),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                    fresh,
                    history,
                }
            }
            Err(reason) => {
                let tick = tick.failed();
                // Nothing was collected, so nothing is acknowledged and the
                // previous history stands.
                let (fresh, history) = (Vec::new(), previous.to_vec());
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
                    session_names: Vec::new(),
                    entries: menu::build_unavailable(&reason),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                    fresh,
                    history,
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
/// The menu carries group headings and separators, so a session's rank is not
/// its menu index. Reading the positions back from the entries keeps the two in
/// step without the menu builder having to report them.
fn rows_for(entries: &[menu::Entry], sessions: &[crate::snapshot::Session]) -> Vec<Row> {
    let mut rows = Vec::new();
    for (menu_index, entry) in entries.iter().enumerate() {
        if let menu::Entry::Action {
            id: menu::ActionId::Session(session_index),
            ..
        } = entry
        {
            if let Some(session) = sessions.get(*session_index) {
                rows.push(Row {
                    menu_index,
                    name: session.name.clone(),
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

/// Keep the newest alerts, without letting one reappear.
///
/// CDX only hands over what it has not seen acknowledged, but a companion that
/// died between drawing and acknowledging will be handed the same alert again.
/// De-duplicating by id here means the menu never shows one twice even then.
fn merge_history(previous: &[Event], fresh: &[Event]) -> Vec<Event> {
    let mut history: Vec<Event> = previous.to_vec();
    for event in fresh {
        if !history.iter().any(|seen| seen.id == event.id) {
            history.push(event.clone());
        }
    }
    let overflow = history.len().saturating_sub(events::HISTORY_LIMIT);
    history.drain(..overflow);
    history
}

#[cfg(test)]
mod tests {
    use super::*;

    fn event(id: &str) -> Event {
        Event {
            id: id.into(),
            kind: "complete".into(),
            title: format!("✓ {id}"),
            message: "m".into(),
        }
    }

    #[test]
    fn an_alert_redelivered_after_a_crash_is_not_shown_twice() {
        let history = merge_history(&[event("a")], &[event("a"), event("b")]);
        assert_eq!(
            history.iter().map(|e| e.id.as_str()).collect::<Vec<_>>(),
            vec!["a", "b"]
        );
    }

    #[test]
    fn the_history_is_bounded_and_keeps_the_newest() {
        let previous: Vec<Event> = (0..events::HISTORY_LIMIT)
            .map(|i| event(&i.to_string()))
            .collect();
        let history = merge_history(&previous, &[event("new")]);
        assert_eq!(history.len(), events::HISTORY_LIMIT);
        assert_eq!(history.last().unwrap().id, "new");
        assert!(!history.iter().any(|e| e.id == "0"));
    }
}
