//! The short-lived "something happened" marker beside the icon.
//!
//! `req_038` asks for a temporary icon hint as well as a menu history, and the
//! two answer different questions. The history answers "what did I miss", on
//! demand. The hint answers "is there anything new", at a glance, without
//! opening anything — and then gets out of the way.
//!
//! It is deliberately *beside* the glyph rather than replacing it. The glyph
//! means remaining quota; swapping it for an alert marker would hide the one
//! thing the icon exists to show, and a user glancing at a critical account
//! would see an envelope instead.
//!
//! It expires on its own. A marker that stayed until clicked would become
//! permanent furniture for anyone running several agents, and a permanent
//! marker says nothing.

use std::time::{Duration, Instant};

/// How long a marker stays. Long enough to catch a glance at the screen,
/// short enough that a busy fleet does not leave it lit all day.
pub const HINT_DURATION: Duration = Duration::from_secs(45);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Hint {
    count: usize,
    until: Instant,
}

impl Hint {
    /// A marker for alerts that just arrived, or None when none did.
    pub fn raised(count: usize, now: Instant) -> Option<Self> {
        if count == 0 {
            return None;
        }
        Some(Hint {
            count,
            until: now + HINT_DURATION,
        })
    }

    pub fn expired(&self, now: Instant) -> bool {
        now >= self.until
    }

    /// What sits next to the icon. A count rather than a dot, because "three
    /// agents finished" and "one did" call for different reactions, and this is
    /// the only surface that can say so without a click.
    pub fn label(&self) -> String {
        format!("●{}", self.count)
    }
}

/// The title to show beside the glyph, given the current hint.
///
/// `None` clears it. Passing the cleared state explicitly rather than leaving
/// the old title in place is what makes the marker temporary at all.
pub fn title(hint: Option<Hint>, now: Instant) -> Option<String> {
    match hint {
        Some(hint) if !hint.expired(now) => Some(hint.label()),
        _ => None,
    }
}

/// Carry a hint forward, raising a new one for fresh alerts and dropping it
/// once it has expired.
pub fn advance(current: Option<Hint>, fresh: usize, now: Instant) -> Option<Hint> {
    if let Some(raised) = Hint::raised(fresh, now) {
        // New alerts restart the window rather than extending the old count:
        // the marker is about what just happened, not a running total the user
        // never asked to accumulate.
        return Some(raised);
    }
    current.filter(|hint| !hint.expired(now))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn now() -> Instant {
        Instant::now()
    }

    #[test]
    fn no_alerts_raises_nothing() {
        assert!(Hint::raised(0, now()).is_none());
        assert!(advance(None, 0, now()).is_none());
    }

    #[test]
    fn the_marker_counts_what_arrived() {
        let hint = advance(None, 3, now()).expect("a hint");
        assert_eq!(hint.label(), "●3");
    }

    #[test]
    fn it_clears_itself_once_the_window_passes() {
        let start = now();
        let hint = advance(None, 1, start);
        let later = start + HINT_DURATION + Duration::from_secs(1);
        assert!(title(hint, later).is_none());
        assert!(advance(hint, 0, later).is_none());
    }

    #[test]
    fn it_survives_a_poll_that_brought_nothing() {
        // Polls are 30-60s apart and the window is 45s, so a hint must not be
        // dropped merely because the next poll was quiet.
        let start = now();
        let hint = advance(None, 2, start);
        let soon = start + Duration::from_secs(20);
        assert_eq!(title(advance(hint, 0, soon), soon).as_deref(), Some("●2"));
    }

    #[test]
    fn new_alerts_replace_the_count_rather_than_accumulating() {
        let start = now();
        let first = advance(None, 5, start);
        let second = advance(first, 1, start + Duration::from_secs(5));
        assert_eq!(second.expect("a hint").label(), "●1");
    }
}
