//! One companion per user session.
//!
//! Two icons in the menu bar is the worst failure this feature has: both are
//! correct, neither is wrong, and the user cannot tell which to quit. So a
//! second launch reports the first and exits rather than drawing beside it.
//!
//! The lock is a file holding a pid. A lock that only recorded "someone is
//! running" would outlive a crash and leave the tray unstartable until the file
//! was found and deleted by hand, which is a worse failure than the one it
//! prevents. Recording the pid lets a stale lock be recognised and reclaimed.

use std::fs;
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug)]
pub struct Lock {
    path: PathBuf,
}

/// Who holds the lock, when someone does.
#[derive(Debug, PartialEq, Eq)]
pub enum Held {
    /// A live companion. Its pid, so the message can name it.
    Running(u32),
    /// A pid file left by a companion that is gone. Reclaimable.
    Stale,
    /// Nothing holds it.
    Free,
}

fn runtime_dir() -> PathBuf {
    // Per-user by construction. On macOS and Linux TMPDIR is already per-user;
    // on Windows LOCALAPPDATA is. A shared /tmp path would make one user's
    // companion block another's on a multi-user machine.
    #[cfg(target_os = "windows")]
    let base = std::env::var("LOCALAPPDATA")
        .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().into());
    #[cfg(not(target_os = "windows"))]
    let base = std::env::temp_dir().to_string_lossy().to_string();
    PathBuf::from(base).join("cdx-tray")
}

fn lock_path() -> PathBuf {
    runtime_dir().join("companion.pid")
}

/// Where the lock lives, for a caller that needs to find it without knowing the
/// rule. The rule differs per platform, and a script or a support conversation
/// that reimplements it would look in the wrong place on exactly the platform
/// where it matters.
pub fn lock_location() -> PathBuf {
    lock_path()
}

/// Is a process with this pid alive?
///
/// On Unix, signal 0 asks exactly that without touching the process. A pid that
/// has been recycled onto some unrelated process would read as alive, which
/// costs a refused launch rather than a duplicate icon: the safe direction.
#[cfg(unix)]
fn is_alive(pid: u32) -> bool {
    // SAFETY: kill with signal 0 performs error checking only, sends nothing.
    unsafe { libc_kill(pid as i32, 0) == 0 }
}

#[cfg(unix)]
extern "C" {
    #[link_name = "kill"]
    fn libc_kill(pid: i32, sig: i32) -> i32;
}

#[cfg(windows)]
fn is_alive(pid: u32) -> bool {
    // tasklist rather than an OpenProcess dance: this runs once at startup, so
    // a process spawn is cheaper than the unsafe surface would be.
    std::process::Command::new("tasklist")
        .args(["/fi", &format!("PID eq {pid}"), "/nh"])
        .output()
        .map(|out| String::from_utf8_lossy(&out.stdout).contains(&pid.to_string()))
        .unwrap_or(false)
}

/// Who holds a named lock file.
///
/// Takes the path rather than assuming the real one, so a test can ask about a
/// lock of its own. The suite used to acquire and release the real lock, which
/// fails on a machine where the companion is running — and worse, `Drop`
/// removes the file, so a run that got past the first assertion would have
/// deleted a live companion's lock and let a second one start.
pub fn holder_at(path: &std::path::Path) -> Held {
    let Ok(contents) = fs::read_to_string(path) else {
        return Held::Free;
    };
    match contents.trim().parse::<u32>() {
        Ok(pid) if is_alive(pid) => Held::Running(pid),
        // Unparseable counts as stale rather than as a hard error: a truncated
        // pid file must not make the tray permanently unstartable.
        _ => Held::Stale,
    }
}

impl Lock {
    /// Take the lock, or report who already holds it.
    pub fn acquire() -> Result<Lock, u32> {
        Lock::acquire_at(lock_path())
    }

    pub fn acquire_at(path: PathBuf) -> Result<Lock, u32> {
        match holder_at(&path) {
            Held::Running(pid) => Err(pid),
            Held::Stale | Held::Free => {
                if let Some(parent) = path.parent() {
                    let _ = fs::create_dir_all(parent);
                }
                if let Ok(mut file) = fs::File::create(&path) {
                    let _ = write!(file, "{}", std::process::id());
                }
                Ok(Lock { path })
            }
        }
    }
}

impl Drop for Lock {
    /// Released on the way out, including on a clean Quit. A crash leaves the
    /// file behind, which is what `Held::Stale` exists to handle.
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_current_process_is_alive_and_a_absurd_pid_is_not() {
        assert!(is_alive(std::process::id()));
        // Above any plausible pid on every platform under test.
        assert!(!is_alive(4_000_000_000));
    }

    #[test]
    fn the_lock_lifecycle() {
        // A lock of its own, never the real one. Using the real path made this
        // fail on any machine where the companion was running — and `Drop`
        // removes the file, so a run that had got past the first assertion
        // would have deleted a live companion's lock and let a second start.
        let path = std::env::temp_dir().join(format!(
            "cdx-tray-test-{}/companion.pid",
            std::process::id()
        ));

        // One test rather than three: they share a single file on disk, and
        // cargo runs tests in parallel, so splitting them would race.
        let lock = Lock::acquire_at(path.clone()).expect("free at first");
        assert_eq!(holder_at(&path), Held::Running(std::process::id()));
        // A second launch sees the first and is told whose pid to deal with.
        assert_eq!(
            Lock::acquire_at(path.clone()).unwrap_err(),
            std::process::id()
        );
        drop(lock);
        assert_eq!(holder_at(&path), Held::Free);

        // A companion that crashed leaves its pid behind. That must be
        // reclaimable, or the tray would be unstartable until someone found
        // and deleted the file by hand.
        fs::write(&path, "4000000000").unwrap();
        assert_eq!(holder_at(&path), Held::Stale);
        fs::write(&path, "not a pid").unwrap();
        assert_eq!(
            holder_at(&path),
            Held::Stale,
            "a truncated file must be reclaimable"
        );
        Lock::acquire_at(path.clone()).expect("a stale lock is reclaimed, not fatal");
        let _ = fs::remove_dir_all(path.parent().unwrap());
    }
}
