//! What the menu shows once the user opens it.
//!
//! Kept apart from the tray backend so it can be tested without a windowing
//! session: the backend turns these entries into `muda` items and nothing more.
//!
//! Two rules from the request drive the shape. The closed icon carries urgency
//! and nothing else, so every name and figure lives here. And no state may be
//! conveyed by colour alone, so each line spells out what it means in text.

use crate::snapshot::{Session, Snapshot, Unavailable};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Entry {
    /// Not selectable. Carries the summary, or the reason there is nothing.
    Info(String),
    Separator,
    Action {
        id: ActionId,
        label: String,
        enabled: bool,
    },
    /// A switch, drawn with a tick so its state is readable without clicking.
    Check {
        id: ActionId,
        label: String,
        checked: bool,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActionId {
    Refresh,
    OpenTerminal,
    Quit,
    /// Silence agent alerts, or let them through again.
    ToggleAlerts,
    /// Open a terminal on this session, by its index in the snapshot.
    ///
    /// An index rather than the name, so the id stays `Copy` and the menu never
    /// carries a session name it would have to keep in step with the snapshot.
    /// The runner resolves it against the same list the menu was built from.
    Session(usize),
}

fn pct(value: Option<f64>) -> String {
    match value {
        Some(v) => format!("{}%", v.round() as i64),
        None => "—".to_string(),
    }
}

/// One line per session: who, which provider, how much is left, and how much
/// that figure can be trusted. `auth_locked` is spelled out rather than shown
/// as staleness, because the user cannot fix it by refreshing.
/// One row, kept short because a dozen of them are read at a glance.
///
/// Columns are not aligned and cannot be: a native menu uses a proportional
/// font, so padding with spaces produces ragged edges that look like a bug.
/// The middle dot separates instead, and the wording is trimmed — "left" and
/// "resets" are obvious from the figure and the arrow, and repeating them
/// thirteen times costs width without telling anyone anything.
fn session_line(session: &Session) -> String {
    let freshness = match session.freshness.as_str() {
        "fresh" => String::new(),
        "auth_locked" => " · running".to_string(),
        "unknown" => " · never reported".to_string(),
        other => format!(" · {other}"),
    };
    let reset = match &session.reset_at {
        Some(at) if !at.is_empty() => format!(" · ↻ {at}"),
        _ => String::new(),
    };
    format!(
        "{} · {} · {}{}{}",
        session.name,
        session.provider,
        pct(session.available_pct),
        freshness,
        reset
    )
}

/// The menu, with a bounded list of recent agent alerts above the actions.
///
/// Alerts sit below the sessions and above the actions on purpose: quota is
/// what the user opened the menu for, and the actions have to stay in the same
/// place whether or not anything happened. Pass an empty slice for no alerts —
/// there is deliberately no second entry point, so no caller can render a menu
/// that silently omits them.
pub fn build_with_alerts(snapshot: &Snapshot, alerts: &[crate::events::Event]) -> Vec<Entry> {
    let mut entries = Vec::new();
    if snapshot.sessions.is_empty() {
        entries.push(Entry::Info("No enabled CDX sessions".into()));
    } else {
        entries.push(Entry::Info(format!(
            "CDX · {} · {} session(s)",
            snapshot.icon_state, snapshot.session_count
        )));
        entries.push(Entry::Separator);
        for (index, session) in snapshot.sessions.iter().enumerate() {
            // An action rather than a label, and that is a readability fix
            // before it is a feature: macOS greys every disabled item, so a
            // dozen informational rows arrive as a wall of grey text. Making
            // them selectable gives them full contrast, and clicking one opens
            // a terminal on that session — which is what the list is for.
            entries.push(Entry::Action {
                id: ActionId::Session(index),
                label: session_line(session),
                enabled: true,
            });
        }
    }
    if !alerts.is_empty() {
        entries.push(Entry::Separator);
        entries.push(Entry::Info("Recent alerts".into()));
        for line in crate::events::history_lines(alerts) {
            entries.push(Entry::Info(line));
        }
    }
    if let Some(hint) = &snapshot.update_hint {
        entries.push(Entry::Separator);
        entries.push(Entry::Info(hint.clone()));
    }
    entries.push(Entry::Separator);
    entries.push(Entry::Check {
        id: ActionId::ToggleAlerts,
        label: "Agent alerts".into(),
        checked: snapshot.alerts_enabled,
    });
    entries.push(refresh_entry(snapshot.refreshable));
    entries.push(Entry::Action {
        id: ActionId::OpenTerminal,
        label: "Open cdx status".into(),
        enabled: true,
    });
    entries.push(Entry::Separator);
    entries.push(Entry::Action {
        id: ActionId::Quit,
        label: "Quit".into(),
        enabled: true,
    });
    entries
}

/// Refresh stays visible but disabled while a session holds the provider auth
/// lock, and says why. Hiding it would leave the user hunting for it; leaving
/// it enabled would promise something that cannot happen.
fn refresh_entry(refreshable: bool) -> Entry {
    if refreshable {
        Entry::Action {
            id: ActionId::Refresh,
            label: "Refresh".into(),
            enabled: true,
        }
    } else {
        Entry::Action {
            id: ActionId::Refresh,
            label: "Refresh unavailable while a session is running".into(),
            enabled: false,
        }
    }
}

/// The menu when `cdx` could not be reached at all. Still a menu, still quitable,
/// and it names the boundary instead of showing a quota that does not exist.
pub fn build_unavailable(reason: &Unavailable) -> Vec<Entry> {
    vec![
        Entry::Info("CDX status unavailable".into()),
        Entry::Info(reason.to_string()),
        Entry::Separator,
        Entry::Action {
            id: ActionId::Refresh,
            label: "Try again".into(),
            enabled: true,
        },
        Entry::Separator,
        Entry::Action {
            id: ActionId::Quit,
            label: "Quit".into(),
            enabled: true,
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::snapshot::{Session, Snapshot};

    fn session(name: &str, pct: Option<f64>, freshness: &str) -> Session {
        Session {
            name: name.into(),
            provider: "codex".into(),
            available_pct: pct,
            freshness: freshness.into(),
            reset_at: None,
        }
    }

    fn snapshot(sessions: Vec<Session>, refreshable: bool) -> Snapshot {
        Snapshot {
            events: Vec::new(),
            alerts_enabled: true,
            icon_state: "low".into(),
            tooltip: "CDX · capacity low".into(),
            session_count: sessions.len() as u64,
            refreshable,
            update_hint: None,
            sessions,
        }
    }

    fn labels(entries: &[Entry]) -> String {
        entries
            .iter()
            .map(|e| match e {
                Entry::Info(text) => text.clone(),
                Entry::Separator => "---".into(),
                Entry::Action { label, .. } | Entry::Check { label, .. } => label.clone(),
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    #[test]
    fn every_session_gets_a_line_with_its_figure_and_its_trust() {
        let entries = build_with_alerts(
            &snapshot(
                vec![
                    session("work", Some(18.0), "fresh"),
                    session("side", None, "unknown"),
                ],
                true,
            ),
            &[],
        );
        let text = labels(&entries);
        assert!(text.contains("work · codex · 18%"), "{text}");
        assert!(text.contains("side · codex · — · never reported"), "{text}");
    }

    #[test]
    fn a_running_session_says_refresh_cannot_help() {
        let entries = build_with_alerts(
            &snapshot(vec![session("work", Some(40.0), "auth_locked")], false),
            &[],
        );
        let text = labels(&entries);
        assert!(text.contains("work · codex · 40% · running"), "{text}");
        // The action stays present so it is not hunted for, but disabled so it
        // does not promise what the auth lock forbids.
        let refresh = entries
            .iter()
            .find_map(|e| match e {
                Entry::Action {
                    id: ActionId::Refresh,
                    enabled,
                    ..
                } => Some(*enabled),
                _ => None,
            })
            .expect("a refresh entry");
        assert!(!refresh);
    }

    #[test]
    fn no_sessions_is_stated_rather_than_shown_as_an_empty_menu() {
        let entries = build_with_alerts(&snapshot(vec![], true), &[]);
        assert!(labels(&entries).contains("No enabled CDX sessions"));
    }

    #[test]
    fn an_update_hint_reaches_the_menu() {
        let mut snap = snapshot(vec![session("work", Some(50.0), "fresh")], true);
        snap.update_hint = Some("Update the tray companion.".into());
        assert!(labels(&build_with_alerts(&snap, &[])).contains("Update the tray companion."));
    }

    #[test]
    fn every_menu_can_be_quit() {
        let quits = |entries: Vec<Entry>| {
            entries.iter().any(|e| {
                matches!(
                    e,
                    Entry::Action {
                        id: ActionId::Quit,
                        ..
                    }
                )
            })
        };
        assert!(quits(build_with_alerts(&snapshot(vec![], true), &[])));
        assert!(quits(build_with_alerts(
            &snapshot(vec![session("w", Some(1.0), "fresh")], false),
            &[]
        )));
        assert!(quits(build_unavailable(&Unavailable::CdxTooOld)));
    }

    #[test]
    fn an_unavailable_menu_names_the_boundary_and_invents_no_quota() {
        let entries = build_unavailable(&Unavailable::CdxTooOld);
        let text = labels(&entries);
        assert!(text.contains("unavailable"), "{text}");
        assert!(
            text.contains("update CDX") || text.contains("Update CDX"),
            "{text}"
        );
        assert!(
            !text.contains('%'),
            "no figure may appear when nothing is known: {text}"
        );
    }
}
