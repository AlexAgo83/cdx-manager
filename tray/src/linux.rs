//! The Linux run loop, on StatusNotifierItem.
//!
//! `ksni` rather than `tray-icon` here, and that is the whole point: `tray-icon`
//! links gtk3, libxdo and libayatana-appindicator, so the Linux asset would
//! refuse to start wherever those packages are absent. `ksni` speaks the same
//! D-Bus protocol in pure Rust, so the binary carries no C prerequisite at all.
//!
//! Support is resolved at runtime by asking the session bus for the watcher,
//! never by matching a distribution or desktop name. GNOME implements
//! StatusNotifierItem only through an extension that Ubuntu ships and a stock
//! GNOME does not, so any name-based guess is wrong on one side or the other.

use std::time::{Duration, Instant};

use std::sync::atomic::{AtomicBool, Ordering};

use crate::events::{clear_terminal, run_plugin_action, set_alerts, set_terminal};
use crate::menu::{ActionId, Entry};
use crate::runner::{announce, Render};
use crate::snapshot::Transport;
use crate::spool;
use crate::unread::Unread;

const PUMP: Duration = Duration::from_millis(200);

/// Whether this session can show a tray icon at all.
///
/// Returns the reason when it cannot, so the caller can say what is missing
/// instead of crashing or drawing nothing.
pub fn tray_support() -> Result<(), String> {
    if std::env::var("DBUS_SESSION_BUS_ADDRESS").is_err() {
        return Err("no D-Bus session bus: this is not a desktop session".into());
    }
    let listed = std::process::Command::new("dbus-send")
        .args([
            "--session",
            "--dest=org.freedesktop.DBus",
            "--type=method_call",
            "--print-reply",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus.ListNames",
        ])
        .output()
        .map_err(|_| "dbus-send is not available to query the session bus".to_string())?;
    if String::from_utf8_lossy(&listed.stdout).contains("org.kde.StatusNotifierWatcher") {
        Ok(())
    } else {
        Err(
            "no org.kde.StatusNotifierWatcher on the session bus: this desktop has no system tray. \
             On GNOME, install the AppIndicator extension."
                .into(),
        )
    }
}

struct CdxTray {
    /// The unread marker, or None.
    hint: Option<String>,
    icon_state: String,
    tooltip: String,
    entries: Vec<Entry>,
    /// Set by a menu click, drained by the loop. The menu callbacks run on
    /// ksni's own thread, so the action has to be handed over rather than acted
    /// on in place.
    pending: std::sync::Arc<std::sync::Mutex<Option<ActionId>>>,
    /// Raised when the root menu is about to be shown, drained by the loop.
    ///
    /// This is the reading signal on Linux, and the only one the protocol
    /// offers: dbusmenu has no closing counterpart, which is why `adr_006`
    /// models opening alone.
    opened: std::sync::Arc<AtomicBool>,
}

impl ksni::Tray for CdxTray {
    fn id(&self) -> String {
        "cdx-tray".into()
    }

    /// Called before the root menu is shown. Nothing is cleared here: the loop
    /// owns the unread state, and this callback runs on ksni's own thread.
    fn menu_about_to_show(&mut self) {
        self.opened.store(true, Ordering::Relaxed);
    }

    fn title(&self) -> String {
        "CDX".into()
    }

    /// The same words CDX composed for every platform. Built there rather than
    /// here so no backend can accidentally say more than the privacy rule
    /// allows, and so the accessibility text is identical everywhere.
    fn tool_tip(&self) -> ksni::ToolTip {
        // StatusNotifierItem has no text beside the icon, so the marker rides
        // on the tooltip here rather than being dropped. The desktop draws the
        // glyph itself from a themed name, which is what keeps it legible on a
        // panel whose colour we do not control — and also why we cannot put a
        // count on it.
        ksni::ToolTip {
            title: match &self.hint {
                Some(marker) => format!("{marker} · {}", self.tooltip),
                None => self.tooltip.clone(),
            },
            ..Default::default()
        }
    }

    /// A themed icon name rather than pixels: SNI desktops draw their own,
    /// which is what keeps the glyph legible on a panel whose colour we do not
    /// control. The names are ordinary freedesktop status icons.
    fn icon_name(&self) -> String {
        match self.icon_state.as_str() {
            "ok" => "user-available",
            "low" => "user-away",
            "critical" => "user-busy",
            _ => "user-offline",
        }
        .into()
    }

    fn menu(&self) -> Vec<ksni::MenuItem<Self>> {
        self.menu_items(&self.entries)
    }
}

impl CdxTray {
    /// One level of entries, so a submenu's contents go through exactly the
    /// same conversion as the root.
    fn menu_items(&self, entries: &[Entry]) -> Vec<ksni::MenuItem<Self>> {
        use ksni::menu::{MenuItem, StandardItem};
        entries
            .iter()
            .map(|entry| match entry {
                Entry::Separator => MenuItem::Separator,
                Entry::Info(text) => StandardItem {
                    label: text.clone(),
                    enabled: false,
                    ..Default::default()
                }
                .into(),
                // StatusNotifierItem has a real checkmark item, so the switch
                // shows its state here as it does on the other two platforms.
                Entry::Check { id, label, checked } => {
                    let action = id.clone();
                    ksni::menu::CheckmarkItem {
                        label: label.clone(),
                        enabled: true,
                        checked: *checked,
                        activate: Box::new(move |tray: &mut CdxTray| {
                            *tray.pending.lock().unwrap() = Some(action.clone());
                        }),
                        ..Default::default()
                    }
                    .into()
                }
                Entry::Action { id, label, enabled } => {
                    let action = id.clone();
                    StandardItem {
                        label: label.clone(),
                        enabled: *enabled,
                        activate: Box::new(move |tray: &mut CdxTray| {
                            *tray.pending.lock().unwrap() = Some(action.clone());
                        }),
                        ..Default::default()
                    }
                    .into()
                }
                // dbusmenu nests natively, so the same rows reach a Linux user
                // through the same structure and no fallback is needed.
                Entry::Submenu { label, items, .. } => ksni::menu::SubMenu {
                    label: label.clone(),
                    submenu: self.menu_items(items),
                    ..Default::default()
                }
                .into(),
            })
            .collect()
    }
}

pub fn run(transport: Transport) -> Result<(), String> {
    tray_support()?;
    let mut unread = Unread::new();
    let mut state = Render::first(&transport, &mut unread);
    let pending = std::sync::Arc::new(std::sync::Mutex::new(None));
    let opened = std::sync::Arc::new(AtomicBool::new(false));
    let mut spool = spool::Spool::idle();
    spool.watch(state.spool_path.as_deref(), transport.is_wsl());
    let handle = ksni::blocking::TrayMethods::spawn(CdxTray {
        hint: unread.marker(),
        icon_state: state.icon_state.clone(),
        tooltip: state.tooltip.clone(),
        entries: state.entries.clone(),
        pending: pending.clone(),
        opened: opened.clone(),
    })
    .map_err(|error| format!("could not register the tray item: {error}"))?;
    // The first draw happens before the loop, so the alerts it showed have to
    // be acknowledged here too. Leaving it to the redraw block would hold them
    // unacknowledged for a whole poll period.
    announce(&transport, &state);

    let mut due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);
    loop {
        std::thread::sleep(PUMP);
        let clicked = pending.lock().unwrap().take();
        // CDX asks for the process, not for the files: an update replaces the
        // binary underneath a companion that would otherwise keep running the
        // old one. Checked before anything else in the iteration so a stop is
        // never delayed by work about to be thrown away.
        if crate::instance::stop_requested() {
            return Ok(());
        }

        let mut redraw = false;
        // The menu the user just opened is the one drawn at the last redraw, so
        // what it showed is what has now been read. Anything that arrived since
        // is not in that set and stays unread.
        if opened.swap(false, Ordering::Relaxed) && unread.consulted() {
            // Rebuild from the same poll, so the list and the badge
            // stop saying different things the moment one changes.
            state.redrawn(&mut unread);
            redraw = true;
        }
        match clicked {
            Some(ActionId::Quit) => return Ok(()),
            Some(ActionId::Refresh) => {
                state = Render::next(&transport, state.tick, &mut unread);
                redraw = true;
            }
            Some(ActionId::OpenTerminal) => open_terminal_in("status", state.terminal.as_deref()),
            Some(ActionId::ToggleAlerts) => {
                set_alerts(&transport, !state.alerts_enabled);
                state = Render::next(&transport, state.tick, &mut unread);
                redraw = true;
            }
            Some(ActionId::SetTerminal(name)) => {
                set_terminal(&transport, &name);
                state = Render::next(&transport, state.tick, &mut unread);
                redraw = true;
            }
            Some(ActionId::ClearTerminal) => {
                clear_terminal(&transport);
                state = Render::next(&transport, state.tick, &mut unread);
                redraw = true;
            }
            Some(ActionId::Session(name)) => open_terminal_in(&name, state.terminal.as_deref()),
            Some(ActionId::FocusTerminal { .. }) => {}
            // A view, not an edit: `cdx config` prints the settings that will
            // apply to the next launch.
            Some(ActionId::SessionConfig(name)) => {
                open_terminal_in(&format!("config {name}"), state.terminal.as_deref())
            }
            Some(ActionId::Plugin { action, root }) => {
                run_plugin_action(&transport, &action, root.as_deref())
            }
            Some(ActionId::AlertGroup) => {}
            None => {}
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
            spool.watch(state.spool_path.as_deref(), transport.is_wsl());
            let icon = state.icon_state.clone();
            let tooltip = state.tooltip.clone();
            let entries = state.entries.clone();
            let marker = unread.marker();
            handle.update(move |tray: &mut CdxTray| {
                tray.icon_state = icon.clone();
                tray.tooltip = tooltip.clone();
                tray.entries = entries.clone();
                tray.hint = marker.clone();
            });
            // Acknowledged only after the alert has been drawn. A companion
            // that dies in between is handed it again next poll and shows it
            // twice at worst; acknowledging first would lose it outright.
            announce(&transport, &state);
            due = Instant::now() + state.delay.unwrap_or(Render::IDLE_WAKEUP);
        }
    }
}

/// Open a terminal on `cdx status`. Best effort, and deliberately not a search
/// through a list of emulators: `x-terminal-emulator` is the distribution's own
/// answer to which terminal this desktop uses.
/// Open a terminal on a cdx subcommand: the status table, or one session.
/// The chosen emulator first, then the list that answers.
///
/// `-e` is the one convention every emulator here honours. The preference names
/// the program, never its arguments, so a value that is not installed costs one
/// failed spawn and the list takes over — a click that opened nothing would be
/// a worse answer than a click that opened the wrong terminal.
fn open_terminal_in(arg: &str, preferred: Option<&str>) {
    let cdx = Transport::cdx_command();
    let defaults = ["x-terminal-emulator", "gnome-terminal", "konsole", "xterm"];
    let terminals: &[&str] = preferred.map_or(&defaults, |terminal| std::slice::from_ref(&terminal));
    for terminal in terminals {
        let text = format!("{cdx} {arg}");
        let mut command = std::process::Command::new(terminal);
        if terminal == "gnome-terminal" {
            command.args(["--tab", "--", "sh", "-lc", &text]);
        } else if terminal == "konsole" {
            command.args(["--new-tab", "-e", "sh", "-lc", &text]);
        } else {
            command.args(["-e", &text]);
        }
        let spawned = command.spawn();
        if spawned.is_ok() {
            return;
        }
    }
    if let Some(terminal) = preferred { eprintln!("Preferred terminal {terminal} is unavailable"); }
}
