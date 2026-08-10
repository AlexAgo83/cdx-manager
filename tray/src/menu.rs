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
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActionId {
    Refresh,
    OpenTerminal,
    Quit,
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
fn session_line(session: &Session) -> String {
    let freshness = match session.freshness.as_str() {
        "fresh" => String::new(),
        "auth_locked" => " · running, cannot refresh".to_string(),
        "unknown" => " · never reported".to_string(),
        other => format!(" · {other}"),
    };
    let reset = match &session.reset_at {
        Some(at) if !at.is_empty() => format!(" · resets {at}"),
        _ => String::new(),
    };
    format!(
        "{} · {} · {} left{}{}",
        session.name,
        session.provider,
        pct(session.available_pct),
        freshness,
        reset
    )
}

pub fn build(snapshot: &Snapshot) -> Vec<Entry> {
    let mut entries = Vec::new();
    if snapshot.sessions.is_empty() {
        entries.push(Entry::Info("No enabled CDX sessions".into()));
    } else {
        entries.push(Entry::Info(format!(
            "CDX · {} · {} session(s)",
            snapshot.icon_state, snapshot.session_count
        )));
        entries.push(Entry::Separator);
        for session in &snapshot.sessions {
            entries.push(Entry::Info(session_line(session)));
        }
    }
    if let Some(hint) = &snapshot.update_hint {
        entries.push(Entry::Separator);
        entries.push(Entry::Info(hint.clone()));
    }
    entries.push(Entry::Separator);
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
            icon_state: "low".into(),
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
                Entry::Action { label, .. } => label.clone(),
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    #[test]
    fn every_session_gets_a_line_with_its_figure_and_its_trust() {
        let entries = build(&snapshot(
            vec![
                session("work", Some(18.0), "fresh"),
                session("side", None, "unknown"),
            ],
            true,
        ));
        let text = labels(&entries);
        assert!(text.contains("work · codex · 18% left"), "{text}");
        assert!(
            text.contains("side · codex · — left · never reported"),
            "{text}"
        );
    }

    #[test]
    fn a_running_session_says_refresh_cannot_help() {
        let entries = build(&snapshot(
            vec![session("work", Some(40.0), "auth_locked")],
            false,
        ));
        let text = labels(&entries);
        assert!(text.contains("running, cannot refresh"), "{text}");
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
        let entries = build(&snapshot(vec![], true));
        assert!(labels(&entries).contains("No enabled CDX sessions"));
    }

    #[test]
    fn an_update_hint_reaches_the_menu() {
        let mut snap = snapshot(vec![session("work", Some(50.0), "fresh")], true);
        snap.update_hint = Some("Update the tray companion.".into());
        assert!(labels(&build(&snap)).contains("Update the tray companion."));
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
        assert!(quits(build(&snapshot(vec![], true))));
        assert!(quits(build(&snapshot(
            vec![session("w", Some(1.0), "fresh")],
            false
        ))));
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
