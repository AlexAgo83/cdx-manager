//! Noticing an alert without waiting for the next poll.
//!
//! The poll period is a budget, not a latency target: `adr_005` fixed it so an
//! idle machine is not kept awake, and at 30 s natively that is fine for a
//! quota figure that changes slowly. It is not fine for an agent alert, which
//! is the one thing the user is actively waiting for — up to thirty seconds
//! between a turn finishing and the banner appearing, where the direct path was
//! instant.
//!
//! No file watcher is needed for it. The event loop already wakes five times a
//! second to drain the platform's queue, so a `stat` on the spool costs
//! microseconds at that rate and turns thirty seconds into two hundred
//! milliseconds.
//!
//! It only works where the companion and CDX share a filesystem. A Windows
//! companion serving CDX from WSL cannot stat a path inside the Linux
//! filesystem, so there the poll period remains the latency, and the code says
//! so rather than quietly doing nothing.

use std::path::PathBuf;
use std::time::SystemTime;

pub struct Spool {
    path: Option<PathBuf>,
    seen: Option<SystemTime>,
}

impl Spool {
    /// Watching nothing, which is the state across WSL and before the first
    /// snapshot has said where the spool lives.
    pub fn idle() -> Self {
        Spool {
            path: None,
            seen: None,
        }
    }

    /// Point at the spool CDX just named, if this companion can reach it.
    ///
    /// Re-reading the path each poll rather than once: `CDX_HOME` can differ
    /// between runs, and a path captured at startup would quietly watch the
    /// wrong file after that.
    pub fn watch(&mut self, path: Option<&str>, across_wsl: bool) {
        let next = match (path, across_wsl) {
            (Some(path), false) if !path.is_empty() => Some(PathBuf::from(path)),
            _ => None,
        };
        if next != self.path {
            self.path = next;
            self.seen = self.modified();
        }
    }

    fn modified(&self) -> Option<SystemTime> {
        std::fs::metadata(self.path.as_ref()?).ok()?.modified().ok()
    }

    /// Whether the spool changed since the last look.
    ///
    /// A missing file reads as unchanged rather than as an event: the spool is
    /// created by the first alert, and treating its absence as news would poll
    /// on every tick until one arrived.
    pub fn changed(&mut self) -> bool {
        if self.path.is_none() {
            return false;
        }
        let now = self.modified();
        if now.is_none() {
            return false;
        }
        if now != self.seen {
            self.seen = now;
            return true;
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn temp(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("cdx-spool-{}-{name}", std::process::id()))
    }

    fn append(path: &PathBuf, text: &str) {
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .unwrap();
        writeln!(file, "{text}").unwrap();
    }

    #[test]
    fn watching_nothing_never_reports_a_change() {
        let mut spool = Spool::idle();
        assert!(!spool.changed());
    }

    #[test]
    fn across_wsl_it_refuses_to_watch() {
        // A Windows process cannot stat a path in the Linux filesystem, so the
        // path is ignored rather than producing a watcher that never fires.
        let path = temp("wsl");
        append(&path, "one");
        let mut spool = Spool::idle();
        spool.watch(Some(path.to_str().unwrap()), true);
        append(&path, "two");
        assert!(!spool.changed());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn an_append_is_noticed_once() {
        let path = temp("append");
        let _ = std::fs::remove_file(&path);
        append(&path, "one");
        let mut spool = Spool::idle();
        spool.watch(Some(path.to_str().unwrap()), false);
        assert!(!spool.changed(), "nothing has happened yet");

        std::thread::sleep(std::time::Duration::from_millis(20));
        append(&path, "two");
        assert!(spool.changed(), "the append should be noticed");
        assert!(!spool.changed(), "and only once");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn a_missing_spool_is_not_news() {
        // The file appears with the first alert. Reading its absence as a
        // change would poll on every tick until one arrived.
        let mut spool = Spool::idle();
        spool.watch(Some(temp("absent").to_str().unwrap()), false);
        assert!(!spool.changed());
        assert!(!spool.changed());
    }
}
