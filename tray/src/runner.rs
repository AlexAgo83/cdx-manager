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
                Render {
                    icon_state: snap.icon_state.clone(),
                    tooltip: snap.tooltip.clone(),
                    alerts_enabled: snap.alerts_enabled,
                    session_names: snap.sessions.iter().map(|s| s.name.clone()).collect(),
                    entries: menu::build_with_alerts(&snap, &history),
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
                    // Unknown reads as on: a CDX we cannot reach must not look
                    // like a mute nobody set.
                    alerts_enabled: true,
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
