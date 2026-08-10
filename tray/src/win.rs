//! The Windows run loop.
//!
//! Same shape as the macOS one, different plumbing: `tray-icon` needs a Win32
//! message pump on the thread that created the icon. `PeekMessageW` rather than
//! `GetMessageW`, because `GetMessageW` blocks until a message arrives and the
//! companion has to wake up on a schedule even when nothing is clicked.
//!
//! This is also the host side of the WSL bridge. Nothing here knows about WSL:
//! `Transport` already turns the poll into a `wsl.exe` call, which is the whole
//! reason the transport is a command rather than a socket.

use std::thread::sleep;
use std::time::{Duration, Instant};

use windows_sys::Win32::UI::WindowsAndMessaging::{
    DispatchMessageW, PeekMessageW, TranslateMessage, MSG, PM_REMOVE, WM_QUIT,
};

use crate::backend;
use crate::menu::ActionId;
use crate::runner::{announce, Render};
use crate::snapshot::Transport;

/// How long the loop sleeps between pumps. Short enough that a click feels
/// immediate, long enough that an idle companion is not a spinning loop.
const PUMP: Duration = Duration::from_millis(100);

pub fn run(transport: Transport) -> Result<(), String> {
    let mut state = Render::first(&transport);
    let (tray, mut actions) =
        backend::build_tray(&state.icon_state, &state.tooltip, &state.entries)?;
    // The first draw happens before the loop, so the alerts it showed have to
    // be acknowledged here too. Leaving it to the redraw block would hold them
    // unacknowledged for a whole poll period, and a companion quit inside that
    // window would have shown an alert CDX still considers undelivered.
    announce(&transport, &state);
    promote_icon();
    let mut due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);

    loop {
        // Drain whatever Windows has queued, without blocking on an empty queue.
        let mut msg: MSG = unsafe { std::mem::zeroed() };
        while unsafe { PeekMessageW(&mut msg, std::ptr::null_mut(), 0, 0, PM_REMOVE) } != 0 {
            if msg.message == WM_QUIT {
                return Ok(());
            }
            unsafe {
                let _ = TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }

        let mut redraw = false;
        while let Ok(event) = muda::MenuEvent::receiver().try_recv() {
            match actions.get(&event.id) {
                Some(ActionId::Quit) => return Ok(()),
                Some(ActionId::Refresh) => {
                    state = Render::next(&transport, state.tick, &state.history);
                    redraw = true;
                }
                Some(ActionId::OpenTerminal) => open_terminal(&transport),
                None => {}
            }
        }

        if Instant::now() >= due {
            state = Render::next(&transport, state.tick, &state.history);
            redraw = true;
        }

        if redraw {
            actions =
                backend::update_tray(&tray, &state.icon_state, &state.tooltip, &state.entries)?;
            due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);
            // Acknowledged only after the alert has been drawn. A companion
            // that dies in between is handed it again next poll and shows it
            // twice at worst; acknowledging first would lose it outright.
            announce(&transport, &state);
        }
        sleep(PUMP);
    }
}

const NOTIFY_ICON_SETTINGS: &str = r"HKCU\Control Panel\NotifyIconSettings";

/// Ask Windows to show the icon rather than bury it in the overflow flyout.
///
/// Windows 11 hides every newly registered notification-area icon behind the
/// chevron. Measured on a real host: the icon was correctly registered and
/// simply not on screen, which defeats the entire point of a status icon.
///
/// Deliberately once, ever, tracked by our own marker file rather than by the
/// registry value. Windows rewrites `IsPromoted` to `0` on its own after the
/// icon first appears, so "absent" is not a reliable "never asked" and reading
/// it would either never promote or promote forever. Once the marker exists the
/// companion never touches the setting again, so unpinning it stays the user's
/// decision. Per-user, no administrator rights.
fn promote_icon() {
    let Some(marker) = promotion_marker() else {
        return;
    };
    if marker.exists() {
        return;
    }
    if let Some(key) = find_icon_key() {
        let _ = std::process::Command::new("reg")
            .args([
                "add",
                &key,
                "/v",
                "IsPromoted",
                "/t",
                "REG_DWORD",
                "/d",
                "1",
                "/f",
            ])
            .output();
    }
    // Written even when the key was not found yet, so a failed attempt does not
    // turn into an attempt on every single launch.
    if let Some(parent) = marker.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(&marker, "1");
}

fn promotion_marker() -> Option<std::path::PathBuf> {
    let base = std::env::var("LOCALAPPDATA").ok()?;
    Some(
        std::path::PathBuf::from(base)
            .join("cdx-tray")
            .join("promoted"),
    )
}

/// The registry subkey Windows created for this executable's icon, if it has
/// appeared yet. Matching on our own path avoids touching another app's entry.
fn find_icon_key() -> Option<String> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.to_string_lossy().to_lowercase();
    let out = std::process::Command::new("reg")
        .args(["query", NOTIFY_ICON_SETTINGS, "/s", "/v", "ExecutablePath"])
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout).to_string();
    let mut current: Option<&str> = None;
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("HKEY_") {
            current = Some(trimmed);
        } else if trimmed.contains("ExecutablePath") && trimmed.to_lowercase().contains(&exe) {
            return current.map(str::to_string);
        }
    }
    None
}

/// Open a console on `cdx status`. When CDX lives in WSL the command has to
/// cross the same way the status poll does, or the window would open on a host
/// that has no `cdx`.
fn open_terminal(transport: &Transport) {
    // The same cdx the status poll uses. Hardcoding `cdx` here would open a
    // console on a different binary than the menu it was clicked from.
    let cdx = Transport::cdx_command();
    let mut command = std::process::Command::new("cmd");
    command.args(["/c", "start", ""]);
    match transport {
        Transport::Wsl { distro: Some(name) } => {
            command.args(["wsl.exe", "-d", name, "--", &cdx, "status"]);
        }
        Transport::Wsl { distro: None } => {
            command.args(["wsl.exe", "--", &cdx, "status"]);
        }
        Transport::Native => {
            command.args(["cmd", "/k", &format!("{cdx} status")]);
        }
    }
    let _ = command.spawn();
}
