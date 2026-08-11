//! What the user has not read yet — the one state behind both the marker and
//! the menu's alert list.
//!
//! Those were two mechanisms answering the same question differently. The
//! marker was a 45-second timer: it said "something just arrived" and then
//! disappeared whether or not anyone had looked, so a user away from the screen
//! for a minute learned nothing. The menu carried a process-lifetime history,
//! so the same alert stayed listed as "recent" long after it had been read, and
//! reading it changed nothing. A badge that clears itself on a timer and a list
//! that never clears cannot agree, and the user could not tell which one meant
//! new information.
//!
//! One list now, and one event that clears it: the menu being opened. `adr_006`
//! settles why opening rather than closing — Linux has no closing signal at
//! all — and why an unobservable signal must never clear: an alert shown again
//! is a nuisance, an alert dropped unseen is the failure this feature exists to
//! prevent.
//!
//! Volatile on purpose. A restarted companion presents everything it is handed
//! as unread, which costs one redundant look and avoids reconciling a persisted
//! read marker against a spool CDX already owns the acknowledgement of.

use crate::events::{Event, HISTORY_LIMIT};

#[derive(Debug, Default)]
pub struct Unread {
    /// Oldest first, bounded by the same limit the menu renders.
    items: Vec<Event>,
    /// The ids in the menu the user is looking at, captured when it was built.
    ///
    /// This is the whole reason an alert arriving mid-consultation survives: it
    /// is not in this list, so the consultation cannot clear it. Reading is
    /// about what was on screen, not about what happened to be unread when the
    /// menu closed.
    drawn: Vec<String>,
}

impl Unread {
    pub fn new() -> Self {
        Self::default()
    }

    /// Take in what this poll delivered.
    ///
    /// De-duplicated by id: CDX only hands over what it has not seen
    /// acknowledged, but a companion that died between drawing and
    /// acknowledging is handed the same alert again, and it must not appear
    /// twice.
    pub fn record(&mut self, fresh: &[Event]) {
        for event in fresh {
            if !self.items.iter().any(|seen| seen.id == event.id) {
                self.items.push(event.clone());
            }
        }
        let overflow = self.items.len().saturating_sub(HISTORY_LIMIT);
        self.items.drain(..overflow);
    }

    pub fn items(&self) -> &[Event] {
        &self.items
    }

    /// Remember what the menu just built is showing.
    ///
    /// Called at every draw rather than at every open, because the draw is the
    /// only moment that knows what went into the menu.
    pub fn mark_drawn(&mut self) {
        self.drawn = self.items.iter().map(|event| event.id.clone()).collect();
    }

    /// The user opened the menu: what was on screen counts as read.
    ///
    /// Returns whether anything changed, so a backend can redraw exactly when
    /// there is something new to show and not on every menu opening.
    pub fn consulted(&mut self) -> bool {
        let before = self.items.len();
        let drawn = std::mem::take(&mut self.drawn);
        self.items.retain(|event| !drawn.contains(&event.id));
        self.items.len() != before
    }

    /// What sits beside the glyph, or `None` when there is nothing to say.
    ///
    /// A count rather than a dot, because "three agents finished" and "one did"
    /// call for different reactions, and this is the only surface that can say
    /// so without a click. Beside the glyph and never instead of it: the glyph
    /// means remaining quota, and a user glancing at a critical account must
    /// not see an envelope in its place.
    pub fn marker(&self) -> Option<String> {
        match self.items.len() {
            0 => None,
            count => Some(format!("●{count}")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::events::Details;

    fn event(id: &str) -> Event {
        Event {
            id: id.into(),
            kind: "complete".into(),
            title: format!("✓ {id}"),
            message: "m".into(),
            details: Details::default(),
        }
    }

    #[test]
    fn the_marker_counts_exactly_what_the_menu_lists() {
        let mut unread = Unread::new();
        unread.record(&[event("a"), event("b")]);
        assert_eq!(unread.marker().as_deref(), Some("●2"));
        assert_eq!(unread.items().len(), 2);
    }

    #[test]
    fn nothing_unread_shows_no_marker() {
        assert!(Unread::new().marker().is_none());
    }

    #[test]
    fn a_consultation_clears_what_was_on_screen() {
        let mut unread = Unread::new();
        unread.record(&[event("a"), event("b")]);
        unread.mark_drawn();
        assert!(unread.consulted());
        assert!(unread.items().is_empty());
        assert!(unread.marker().is_none());
    }

    /// The case the request is about, and the reason reading is measured
    /// against the drawn menu rather than against the list as it stands: an
    /// agent finishing while the menu is open has not been read by anyone.
    #[test]
    fn an_alert_arriving_during_the_consultation_stays_unread() {
        let mut unread = Unread::new();
        unread.record(&[event("seen")]);
        unread.mark_drawn();
        unread.record(&[event("landed-while-open")]);
        unread.consulted();
        assert_eq!(
            unread
                .items()
                .iter()
                .map(|e| e.id.as_str())
                .collect::<Vec<_>>(),
            vec!["landed-while-open"]
        );
        assert_eq!(unread.marker().as_deref(), Some("●1"));
    }

    /// Fail closed. A backend that could not install its menu-open signal never
    /// calls `consulted`, and the marker stays lit rather than clearing on a
    /// reading that never happened.
    #[test]
    fn without_a_consultation_nothing_is_ever_cleared() {
        let mut unread = Unread::new();
        unread.record(&[event("a")]);
        unread.mark_drawn();
        unread.record(&[event("b")]);
        assert_eq!(unread.marker().as_deref(), Some("●2"));
    }

    #[test]
    fn a_second_consultation_without_a_redraw_clears_nothing_twice() {
        let mut unread = Unread::new();
        unread.record(&[event("a")]);
        unread.mark_drawn();
        assert!(unread.consulted());
        // No redraw happened in between, so nothing was on screen to read.
        unread.record(&[event("b")]);
        assert!(!unread.consulted());
        assert_eq!(unread.marker().as_deref(), Some("●1"));
    }

    #[test]
    fn a_redelivered_alert_is_not_listed_twice() {
        let mut unread = Unread::new();
        unread.record(&[event("a")]);
        unread.record(&[event("a"), event("b")]);
        assert_eq!(unread.items().len(), 2);
    }

    #[test]
    fn the_list_is_bounded_and_keeps_the_newest() {
        let mut unread = Unread::new();
        let many: Vec<Event> = (0..HISTORY_LIMIT + 3)
            .map(|i| event(&i.to_string()))
            .collect();
        unread.record(&many);
        assert_eq!(unread.items().len(), HISTORY_LIMIT);
        assert_eq!(
            unread.items().last().unwrap().id,
            (HISTORY_LIMIT + 2).to_string()
        );
        assert!(!unread.items().iter().any(|e| e.id == "0"));
    }
}
