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
use crate::runner::Render;
use crate::snapshot::Transport;

/// How long the loop sleeps between pumps. Short enough that a click feels
/// immediate, long enough that an idle companion is not a spinning loop.
const PUMP: Duration = Duration::from_millis(100);

pub fn run(transport: Transport) -> Result<(), String> {
    let mut state = Render::first(&transport);
    let (tray, mut actions) = backend::build_tray(&state.icon_state, &state.entries)?;
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
                    state = Render::next(&transport, state.tick);
                    redraw = true;
                }
                Some(ActionId::OpenTerminal) => open_terminal(&transport),
                None => {}
            }
        }

        if Instant::now() >= due {
            state = Render::next(&transport, state.tick);
            redraw = true;
        }

        if redraw {
            actions = backend::update_tray(&tray, &state.icon_state, &state.entries)?;
            due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);
        }
        sleep(PUMP);
    }
}

/// Open a console on `cdx status`. When CDX lives in WSL the command has to
/// cross the same way the status poll does, or the window would open on a host
/// that has no `cdx`.
fn open_terminal(transport: &Transport) {
    let mut command = std::process::Command::new("cmd");
    command.args(["/c", "start", ""]);
    match transport {
        Transport::Wsl { distro: Some(name) } => {
            command.args(["wsl.exe", "-d", name, "--", "cdx", "status"]);
        }
        Transport::Wsl { distro: None } => {
            command.args(["wsl.exe", "--", "cdx", "status"]);
        }
        Transport::Native => {
            command.args(["cmd", "/k", "cdx status"]);
        }
    }
    let _ = command.spawn();
}
