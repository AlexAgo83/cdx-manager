//! What one poll produced: what to draw, and when to poll again.
//!
//! Shared by every platform loop. The loops differ only in how they pump their
//! event queue; what they show and when they ask again is decided here, so the
//! macOS and Windows companions cannot drift apart in behaviour.

use std::time::Duration;

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
}

impl Render {
    /// How long to wait when there is nothing to poll for. Rarely rather than
    /// never, so enabling a session later is eventually noticed without the
    /// user having to restart the companion.
    pub const IDLE_WAKEUP: Duration = Duration::from_secs(3600);

    pub fn first(transport: &Transport) -> Self {
        Self::next(transport, Tick::start())
    }

    pub fn next(transport: &Transport, tick: Tick) -> Self {
        match fetch(transport) {
            Ok(snap) => {
                let tick = tick.succeeded(snap.session_count);
                Render {
                    icon_state: snap.icon_state.clone(),
                    tooltip: snap.tooltip.clone(),
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
                    tooltip: format!("CDX · unavailable · {reason}"),
                    entries: menu::build_unavailable(&reason),
                    delay: tick.next_delay(transport.is_wsl()),
                    tick,
                }
            }
        }
    }
}
