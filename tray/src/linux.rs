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

use crate::events::set_alerts;
use crate::hint;
use crate::menu::{ActionId, Entry};
use crate::runner::{announce, Render};
use crate::snapshot::Transport;

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
    /// The short-lived "something arrived" marker, or None.
    hint: Option<String>,
    icon_state: String,
    tooltip: String,
    entries: Vec<Entry>,
    /// Set by a menu click, drained by the loop. The menu callbacks run on
    /// ksni's own thread, so the action has to be handed over rather than acted
    /// on in place.
    pending: std::sync::Arc<std::sync::Mutex<Option<ActionId>>>,
}

impl ksni::Tray for CdxTray {
    fn id(&self) -> String {
        "cdx-tray".into()
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
        use ksni::menu::{MenuItem, StandardItem};
        self.entries
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
                    let action = *id;
                    ksni::menu::CheckmarkItem {
                        label: label.clone(),
                        enabled: true,
                        checked: *checked,
                        activate: Box::new(move |tray: &mut CdxTray| {
                            *tray.pending.lock().unwrap() = Some(action);
                        }),
                        ..Default::default()
                    }
                    .into()
                }
                Entry::Action { id, label, enabled } => {
                    let action = *id;
                    StandardItem {
                        label: label.clone(),
                        enabled: *enabled,
                        activate: Box::new(move |tray: &mut CdxTray| {
                            *tray.pending.lock().unwrap() = Some(action);
                        }),
                        ..Default::default()
                    }
                    .into()
                }
            })
            .collect()
    }
}

pub fn run(transport: Transport) -> Result<(), String> {
    tray_support()?;
    let mut state = Render::first(&transport);
    let pending = std::sync::Arc::new(std::sync::Mutex::new(None));
    let mut alert_hint = hint::advance(None, state.fresh.len(), Instant::now());
    let handle = ksni::blocking::TrayMethods::spawn(CdxTray {
        hint: hint::title(alert_hint, Instant::now()),
        icon_state: state.icon_state.clone(),
        tooltip: state.tooltip.clone(),
        entries: state.entries.clone(),
        pending: pending.clone(),
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
        let mut redraw = false;
        match clicked {
            Some(ActionId::Quit) => return Ok(()),
            Some(ActionId::Refresh) => {
                state = Render::next(&transport, state.tick, &state.history);
                redraw = true;
            }
            Some(ActionId::OpenTerminal) => open_terminal("status"),
            Some(ActionId::ToggleAlerts) => {
                set_alerts(&transport, !state.alerts_enabled);
                state = Render::next(&transport, state.tick, &state.history);
                redraw = true;
            }
            Some(ActionId::Session(index)) => {
                if let Some(name) = state.session_names.get(index) {
                    open_terminal(name);
                }
            }
            None => {}
        }
        if Instant::now() >= due {
            state = Render::next(&transport, state.tick, &state.history);
            redraw = true;
        }
        if redraw {
            alert_hint = hint::advance(alert_hint, state.fresh.len(), Instant::now());
            let icon = state.icon_state.clone();
            let tooltip = state.tooltip.clone();
            let entries = state.entries.clone();
            let marker = hint::title(alert_hint, Instant::now());
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
fn open_terminal(arg: &str) {
    let cdx = Transport::cdx_command();
    for terminal in ["x-terminal-emulator", "gnome-terminal", "konsole", "xterm"] {
        let spawned = std::process::Command::new(terminal)
            .args(["-e", &format!("{cdx} {arg}")])
            .spawn();
        if spawned.is_ok() {
            return;
        }
    }
}
