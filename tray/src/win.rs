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

use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};
use std::thread::sleep;
use std::time::{Duration, Instant};

use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CallWindowProcW, DispatchMessageW, PeekMessageW, SetWindowLongPtrW, TranslateMessage,
    GWLP_WNDPROC, MSG, PM_REMOVE, WM_INITMENUPOPUP, WM_QUIT, WNDPROC,
};

use crate::backend;
use crate::events::set_alerts;
use crate::menu::ActionId;
use crate::runner::{announce, Render};
use crate::snapshot::Transport;
use crate::spool;
use crate::unread::Unread;

/// How long the loop sleeps between pumps. Short enough that a click feels
/// immediate, long enough that an idle companion is not a spinning loop.
const PUMP: Duration = Duration::from_millis(100);

/// Raised by the subclassed window procedure, drained by the loop.
static MENU_OPENED: AtomicBool = AtomicBool::new(false);
/// The window procedure `tray-icon` installed, which ours must still call.
static PREVIOUS_PROC: AtomicIsize = AtomicIsize::new(0);

/// See the menu open.
///
/// `tray-icon` shows the menu itself, with `TrackPopupMenu` on a window it owns
/// and exposes, and it handles none of the menu messages — so `WM_INITMENUPOPUP`
/// on that window is free to take, and it is the reading signal `adr_006` asks
/// for. Nothing is cleared here: `TrackPopupMenu` is modal, so this runs inside
/// a loop that owns the thread until the menu closes. The flag is drained when
/// the pump resumes, which is the earliest moment the loop exists again.
unsafe extern "system" fn observe_menu(
    hwnd: HWND,
    message: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    if message == WM_INITMENUPOPUP {
        MENU_OPENED.store(true, Ordering::Relaxed);
    }
    let previous: WNDPROC = std::mem::transmute(PREVIOUS_PROC.load(Ordering::Relaxed));
    CallWindowProcW(previous, hwnd, message, wparam, lparam)
}

/// Install the observer, reporting whether it took.
///
/// A false here is not an error to surface: the companion works without the
/// signal, it simply never marks anything read, which is the failing-closed
/// behaviour `adr_006` requires.
fn observe_menu_openings(tray: &tray_icon::TrayIcon) -> bool {
    let hwnd = tray.window_handle();
    if hwnd.is_null() {
        return false;
    }
    // SAFETY: the hwnd belongs to the tray icon and outlives it; the previous
    // procedure is stored before ours can be called, because the window has no
    // messages to dispatch until this thread pumps again.
    // Through a typed function pointer rather than casting the function item
    // straight to an integer, which clippy rightly refuses: the item's type is
    // not the pointer Windows is being handed.
    let ours: unsafe extern "system" fn(HWND, u32, WPARAM, LPARAM) -> LRESULT = observe_menu;
    let previous = unsafe { SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ours as usize as isize) };
    if previous == 0 {
        return false;
    }
    PREVIOUS_PROC.store(previous, Ordering::Relaxed);
    true
}

pub fn run(transport: Transport) -> Result<(), String> {
    let mut unread = Unread::new();
    let mut state = Render::first(&transport, &mut unread);
    let (tray, mut actions) = backend::build_tray(
        &state.icon_state,
        &state.tooltip,
        &state.entries,
        &state.rows,
    )?;
    // The first draw happens before the loop, so the alerts it showed have to
    // be acknowledged here too. Leaving it to the redraw block would hold them
    // unacknowledged for a whole poll period, and a companion quit inside that
    // window would have shown an alert CDX still considers undelivered.
    let mut spool = spool::Spool::idle();
    spool.watch(state.spool_path.as_deref(), transport.is_wsl());
    let observing = observe_menu_openings(&tray);
    backend::set_title(&tray, unread.marker());
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
        // Drained after the pump, because the pump is where the modal menu
        // loop ran: nothing else on this thread could have observed it. The
        // menu that was open is the one drawn at the last redraw, so what it
        // showed is what has been read, and an alert that landed while it was
        // open is not in that set.
        if observing && MENU_OPENED.swap(false, Ordering::Relaxed) && unread.consulted() {
            redraw = true;
        }
        while let Ok(event) = muda::MenuEvent::receiver().try_recv() {
            match actions.get(&event.id) {
                Some(ActionId::Quit) => return Ok(()),
                Some(ActionId::Refresh) => {
                    state = Render::next(&transport, state.tick, &mut unread);
                    redraw = true;
                }
                Some(ActionId::OpenTerminal) => open_terminal(&transport, "status"),
                Some(ActionId::ToggleAlerts) => {
                    // Written through cdx rather than by the companion: the
                    // hook is what obeys the mute, and it reads CDX's store.
                    // The next poll brings the new state back, so the tick
                    // reflects what was actually recorded rather than what was
                    // clicked.
                    set_alerts(&transport, !state.alerts_enabled);
                    state = Render::next(&transport, state.tick, &mut unread);
                    redraw = true;
                }
                Some(ActionId::Session(name)) => open_terminal(&transport, name),
                // A view, not an edit: `cdx config` prints the settings that
                // will apply to the next launch, through the same native or
                // WSL routing every other tray command uses.
                Some(ActionId::SessionConfig(name)) => {
                    open_terminal(&transport, &format!("config {name}"))
                }
                None => {}
            }
        }

        // An alert lands in the spool the moment a hook writes it. Polling for
        // it would cost up to a full period of latency on the one event the
        // user is actually waiting for, so a change pulls the next poll forward
        // instead.
        if spool.changed() {
            due = Instant::now();
        }
        if Instant::now() >= due {
            state = Render::next(&transport, state.tick, &mut unread);
            redraw = true;
        }

        if redraw {
            actions = backend::update_tray(
                &tray,
                &state.icon_state,
                &state.tooltip,
                unread.marker(),
                &state.entries,
                &state.rows,
            )?;
            due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);
            // Acknowledged only after the alert has been drawn. A companion
            // that dies in between is handed it again next poll and shows it
            // twice at worst; acknowledging first would lose it outright.
            spool.watch(state.spool_path.as_deref(), transport.is_wsl());
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
/// Open a console on a cdx subcommand: the status table, or one session.
fn open_terminal(transport: &Transport, arg: &str) {
    // The same cdx the status poll uses. Hardcoding `cdx` here would open a
    // console on a different binary than the menu it was clicked from.
    let cdx = Transport::cdx_command();
    let mut command = std::process::Command::new("cmd");
    command.args(["/c", "start", ""]);
    match transport {
        Transport::Wsl { distro: Some(name) } => {
            command.args(["wsl.exe", "-d", name, "--", &cdx, arg]);
        }
        Transport::Wsl { distro: None } => {
            command.args(["wsl.exe", "--", &cdx, arg]);
        }
        Transport::Native => {
            command.args(["cmd", "/k", &format!("{cdx} {arg}")]);
        }
    }
    let _ = command.spawn();
}
