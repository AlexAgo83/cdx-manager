//! When the companion is allowed to ask `cdx` again.
//!
//! The whole point of this module is that polling has a cost the user pays.
//! Natively it is a Python process; across WSL every tick is a `wsl.exe` call
//! that costs 100-300 ms and keeps the WSL VM awake, defeating `vmIdleTimeout`.
//! `adr_005` fixes the budget, and this is where it is enforced rather than
//! left to whoever writes the loop.

use std::time::Duration;

pub const NATIVE_PERIOD: Duration = Duration::from_secs(30);
pub const WSL_PERIOD: Duration = Duration::from_secs(60);
pub const BACKOFF_PERIOD: Duration = Duration::from_secs(300);
/// Consecutive failures before backing off. Two is noise on a laptop waking
/// from sleep; three means something is actually wrong.
pub const BACKOFF_AFTER: u32 = 3;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Tick {
    pub consecutive_failures: u32,
    pub session_count: u64,
}

impl Tick {
    pub fn start() -> Self {
        Tick {
            consecutive_failures: 0,
            session_count: 0,
        }
    }

    pub fn succeeded(self, session_count: u64) -> Self {
        Tick {
            consecutive_failures: 0,
            session_count,
        }
    }

    /// A failed read keeps the last known session count: a transient error is
    /// not evidence that the user removed every session, and treating it as
    /// such would stop polling exactly when something needs attention.
    pub fn failed(self) -> Self {
        Tick {
            consecutive_failures: self.consecutive_failures.saturating_add(1),
            ..self
        }
    }

    /// `None` means stop polling entirely until something asks for a refresh.
    ///
    /// With no enabled session there is nothing to report, so a background
    /// process that keeps calling `cdx` is pure cost. This is the difference
    /// between a status icon and a battery drain.
    pub fn next_delay(&self, across_wsl: bool) -> Option<Duration> {
        if self.session_count == 0 && self.consecutive_failures == 0 {
            return None;
        }
        if self.consecutive_failures >= BACKOFF_AFTER {
            return Some(BACKOFF_PERIOD);
        }
        Some(if across_wsl {
            WSL_PERIOD
        } else {
            NATIVE_PERIOD
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn polls_at_the_platform_period() {
        let tick = Tick::start().succeeded(2);
        assert_eq!(tick.next_delay(false), Some(NATIVE_PERIOD));
        assert_eq!(tick.next_delay(true), Some(WSL_PERIOD));
    }

    #[test]
    fn stops_entirely_when_no_session_is_enabled() {
        assert_eq!(Tick::start().succeeded(0).next_delay(false), None);
        assert_eq!(Tick::start().succeeded(0).next_delay(true), None);
    }

    #[test]
    fn backs_off_only_after_repeated_failures() {
        let mut tick = Tick::start().succeeded(1);
        for _ in 0..BACKOFF_AFTER - 1 {
            tick = tick.failed();
            assert_eq!(
                tick.next_delay(true),
                Some(WSL_PERIOD),
                "one failure is noise"
            );
        }
        tick = tick.failed();
        assert_eq!(tick.next_delay(true), Some(BACKOFF_PERIOD));
    }

    #[test]
    fn a_success_clears_the_back_off() {
        let tick = Tick::start().succeeded(1).failed().failed().failed();
        assert_eq!(tick.next_delay(false), Some(BACKOFF_PERIOD));
        assert_eq!(tick.succeeded(1).next_delay(false), Some(NATIVE_PERIOD));
    }

    #[test]
    fn keeps_polling_while_failing_even_with_no_known_sessions() {
        // A failure must not be read as "the user has no sessions", or the
        // companion would go silent for good on the first hiccup.
        let tick = Tick::start().failed();
        assert_eq!(tick.session_count, 0);
        assert_eq!(tick.next_delay(false), Some(NATIVE_PERIOD));
    }
}
