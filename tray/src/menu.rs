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
    /// A row that opens into its own actions.
    ///
    /// `about` says what the submenu is for, and it is not decoration: the
    /// drawn macOS cell is bound to a row by it, so the cell, the label and
    /// every action inside cannot come apart from the session they describe.
    Submenu {
        about: ActionId,
        label: String,
        items: Vec<Entry>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ActionId {
    Refresh,
    OpenTerminal,
    Quit,
    /// Silence agent alerts, or let them through again.
    ToggleAlerts,
    SetTerminal(String),
    /// Open a terminal on this session, by name.
    ///
    /// It was an index into the snapshot, which kept the id `Copy`. That only
    /// held while the order was stable: now that the menu is ordered by
    /// remaining capacity, a poll landing between the draw and the click
    /// renumbers the list, and a rank would open whichever session had taken
    /// that place. The name is what the user clicked and stays what gets opened.
    Session(String),
    FocusTerminal { kind: String, id: String },
    /// One card action, named by the id CDX published for it.
    ///
    /// Carried verbatim and handed straight back: the companion does not know
    /// what any of them do, and cannot compose one, which is what keeps an
    /// integration from reaching the machine through the tray.
    Plugin {
        action: String,
        root: Option<String>,
    },
    /// A non-actionable alert submenu. Kept distinct from `Session` so macOS
    /// never mistakes it for a capacity row when drawing native cells.
    AlertGroup,
    /// Show this session's persistent launch settings, by name.
    ///
    /// A view, never an edit, and the wording says so: these settings apply to
    /// the next launch. A tray that let you change the model of an assistant
    /// already mid-turn would be lying about what it can do — CDX writes them
    /// for the next launch, and no provider accepts them for a running process.
    SessionConfig(String),
}

/// Whether a session action can be offered, and why not when it cannot.
///
/// An unavailable action is drawn disabled with its reason rather than hidden,
/// because a control that vanishes silently reads as a bug; only an action this
/// build knows nothing about is absent entirely.
///
/// `Unavailable` is the half of the contract nothing declares yet: the two
/// built-in actions are always offered, and the first extension to arrive is
/// what will construct it. Kept and tested rather than deferred, so an action
/// that cannot run has a defined rendering the day one exists.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Availability {
    Available,
    #[allow(dead_code)]
    Unavailable(String),
}

/// One action a session row offers, declared rather than hard-coded into the
/// menu builder.
///
/// This is the seam `req_043` AC4 asks for: an extension — a Logics action, say
/// — becomes another declared entry here once the plugin contract validates it,
/// and nothing else in the menu has to learn about it. Until something declares
/// one, the list is exactly the two built-ins, and no empty "Extensions"
/// heading is rendered to advertise a feature that is not there.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionAction {
    pub id: ActionId,
    pub label: String,
    pub availability: Availability,
}

/// Eight blocks of remaining capacity.
///
/// `req_035` AC4 asks for a gauge and this is it: a bare percentage makes you
/// read thirteen numbers to find the low one, where a bar is scanned. It leads
/// the line because block characters all have the same advance width, so the
/// gauge column aligns exactly even in the proportional font a native menu
/// uses — the ragged part ends up on the right, where nothing is being
/// compared. The figure stays beside it: `req_038` AC4 forbids making shape the
/// only signal.
const GAUGE_WIDTH: usize = 8;

/// A full block for what is left, a thin one for what is gone.
///
/// Two attempts got here. It was `█` and `░`: the right widths, but the light
/// shade is a dither pattern, and on a dark Windows menu a row of them reads as
/// corrupted text. Then `━` and `─`, which fixed that and lost the point — at
/// menu font size the heavy and light box-drawing lines are indistinguishable,
/// so every session showed the same flat line and the gauge said nothing.
///
/// Both characters stay inside Block Elements, which is what guarantees the
/// identical advance width the column depends on: a proportional menu font
/// makes spaces useless for alignment, and a mixed-block pair would leave the
/// right edge ragged. The eighth-height block draws a thin rule rather than a
/// texture, so the contrast is unmistakable and nothing dithers.
///
/// None of this was visible from the machine it was written on: macOS draws its
/// own cell and never renders these at all.
const FILLED: &str = "█";
const EMPTY: &str = "▁";

fn gauge(value: Option<f64>) -> String {
    let filled = match value {
        // Never reported draws empty rather than full: an unknown session must
        // not look like a healthy one at a glance.
        None => 0,
        Some(v) => ((v.clamp(0.0, 100.0) / 100.0) * GAUGE_WIDTH as f64).round() as usize,
    };
    format!(
        "{}{}",
        FILLED.repeat(filled),
        EMPTY.repeat(GAUGE_WIDTH - filled.min(GAUGE_WIDTH))
    )
}

/// The severity a figure carries, named as the icon names it.
///
/// Read only where a platform can colour something, which today is the macOS
/// cell alone. It stays here rather than moving there because it is the one
/// definition of what low and critical mean, and the glyph CDX chooses uses
/// the same thresholds — two copies is how a bar and an icon end up
/// disagreeing about the same session.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
pub fn state_for(value: Option<f64>) -> &'static str {
    match value {
        None => "unknown",
        Some(v) if v < 5.0 => "critical",
        Some(v) if v < 25.0 => "low",
        Some(_) => "ok",
    }
}

pub fn pct(value: Option<f64>) -> String {
    match value {
        Some(v) => format!("{}%", v.round() as i64),
        None => "—".to_string(),
    }
}

/// The windows a session reports, each named.
///
/// Both providers meter two: five hours and a week. Showing one number meant
/// showing whichever CDX had decided was worse, so a week almost spent was
/// invisible behind a five-hour window that had just reset — and the figure
/// silently changed meaning between two polls.
///
/// Named rather than positional: "5h 40% · wk 12%" survives one of the two
/// being absent, where a bare "40% · 12%" would not say which one went.
pub fn windows(session: &Session) -> Vec<(&'static str, Option<f64>)> {
    let mut reported = Vec::new();
    if session.five_hour_pct.is_some() {
        reported.push(("5h", session.five_hour_pct));
    }
    if session.week_pct.is_some() {
        reported.push(("wk", session.week_pct));
    }
    // A provider that reports neither window still has a figure: CDX derives
    // `available_pct` from whatever it had, and an empty row would be a
    // regression for the sake of a distinction that does not apply here.
    if reported.is_empty() {
        reported.push(("", session.available_pct));
    }
    reported
}

fn windows_text(session: &Session) -> String {
    windows(session)
        .into_iter()
        .map(|(name, value)| match name {
            "" => pct(value),
            _ => format!("{name} {}", pct(value)),
        })
        .collect::<Vec<_>>()
        .join(" · ")
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
/// How much the figure can be trusted, in words.
///
/// Empty when the figure is current: a text row that said "fresh" thirteen
/// times would spend width on the absence of a problem. The drawn row asks for
/// the age instead — see `row_detail` — because a cell with an empty second
/// line looks broken where an unadorned text row does not.
///
/// Shared with the drawn row so the two cannot describe the same session
/// differently, which is exactly how the provider and the reset went missing
/// from the macOS cell in the first place.
pub fn freshness_words(session: &Session) -> String {
    // Stale says the figure is old; the age says how old, which is the part a
    // reader can act on. "stale 3h ago" beats "stale" and costs six characters.
    match session.freshness.as_str() {
        "fresh" => String::new(),
        "auth_locked" => "running".to_string(),
        "unknown" => "never reported".to_string(),
        other => match &session.updated_ago {
            Some(ago) => format!("{other} {ago}"),
            None => other.to_string(),
        },
    }
}

/// When the limit resets, or nothing when CDX does not know.
///
/// The distance first, the stamp only when CDX is too old to have computed one
/// — never both, since they say the same thing at different lengths.
pub fn reset_words(session: &Session) -> String {
    match (&session.reset_in, &session.reset_at) {
        (Some(distance), _) => format!("↻ {distance}"),
        (None, Some(at)) if !at.is_empty() => format!("↻ {at}"),
        _ => String::new(),
    }
}

/// The drawn row's second line: how old the figure is, and when it resets.
///
/// A current figure says its age here rather than nothing. On a text row the
/// absence of a warning means current; a drawn cell has a line reserved for
/// this, and leaving it blank reads as missing data rather than as good news.
/// It is also the question the operator asked first: a percentage with no age
/// cannot be acted on.
pub fn row_detail(session: &Session) -> String {
    let freshness = match (session.freshness.as_str(), &session.updated_ago) {
        ("fresh", Some(ago)) => ago.clone(),
        ("fresh", None) => "just now".to_string(),
        _ => freshness_words(session),
    };
    [freshness, reset_words(session)]
        .into_iter()
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join(" · ")
}

fn session_line(session: &Session) -> String {
    let freshness = match freshness_words(session) {
        words if words.is_empty() => String::new(),
        words => format!(" · {words}"),
    };
    let reset = match reset_words(session) {
        words if words.is_empty() => String::new(),
        words => format!(" · {words}"),
    };
    // The provider rides on the row now. It used to be a group heading, which
    // cost less width but reordered the list: grouping gives a provider the rank
    // of its most constrained session, so a healthy account could sit above the
    // one that made the icon turn. The list is ordered by remaining capacity and
    // by nothing else, so the provider has to be said per row.
    // The leading gauge stays on the window that runs out first: it is the
    // column the eye scans down, and it has to mean one thing all the way.
    format!(
        "  {}  {}  {} · {}{}{}",
        gauge(session.available_pct),
        windows_text(session),
        session.name,
        session.provider,
        freshness,
        reset
    )
}

/// The wording for a card-wide action, or None when this build has no name for
/// it. The verb is the part that matters; the plugin prefix is routing.
fn plugin_action_label(action: &str) -> Option<String> {
    match action.split_once('.') {
        Some(("logics", "open")) => Some("  Open Logics".to_string()),
        Some(("logics", "refresh")) => Some("  Refresh Logics".to_string()),
        _ => None,
    }
}

/// What one session row offers, as declared actions.
///
/// Two built-ins today. Opening keeps exactly the behaviour the row used to
/// have on click, so nothing was taken away by making it explicit. Viewing the
/// launch settings names the next launch in the label itself: CDX stores them
/// for the next start, no provider accepts them for a process already running,
/// and a tray that implied otherwise would be the misleading surface this work
/// exists to avoid.
pub fn session_actions(session: &Session) -> Vec<SessionAction> {
    vec![
        SessionAction {
            id: ActionId::Session(session.name.clone()),
            label: "Open session".into(),
            availability: Availability::Available,
        },
        SessionAction {
            id: ActionId::SessionConfig(session.name.clone()),
            label: "Launch settings (next launch)".into(),
            availability: Availability::Available,
        },
    ]
}

/// The declared actions as menu entries.
///
/// An unavailable action stays visible and disabled, carrying its reason, so
/// the user learns why rather than wondering where it went.
fn session_entries(session: &Session) -> Vec<Entry> {
    session_entries_from(session_actions(session))
}

fn session_entries_from(actions: Vec<SessionAction>) -> Vec<Entry> {
    actions
        .into_iter()
        .map(|action| match action.availability {
            Availability::Available => Entry::Action {
                id: action.id,
                label: action.label,
                enabled: true,
            },
            Availability::Unavailable(reason) => Entry::Action {
                id: action.id,
                label: format!("{} — {reason}", action.label),
                enabled: false,
            },
        })
        .collect()
}

/// The menu, with the unread agent alerts above the actions.
///
/// Alerts sit below the sessions and above the actions on purpose: quota is
/// what the user opened the menu for, and the actions have to stay in the same
/// place whether or not anything happened. Pass an empty slice for no alerts —
/// there is deliberately no second entry point, so no caller can render a menu
/// that silently omits them.
///
/// What arrives here is the unread list, not a history: showing this menu is
/// what marks these read, so the section is empty the next time it is opened
/// unless something new arrived. That is the point of `req_042` — the count
/// beside the icon and this list are the same thing said twice.
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
        for session in &snapshot.sessions {
            // A submenu rather than a direct launch, and that is a truthfulness
            // fix before it is a feature: a row that launched on click had no
            // room to offer anything else, so every other thing a user might
            // want from a session had nowhere to live. Opening is now one named
            // action among the row's actions rather than the only thing a click
            // can mean.
            entries.push(Entry::Submenu {
                about: ActionId::Session(session.name.clone()),
                label: session_line(session),
                items: session_entries(session),
            });
        }
    }
    // Integration cards sit below the sessions and above the alerts: quota is
    // what the menu is for, alerts are what just happened, and a card is
    // standing context that should not push either of them down the menu.
    for card in &snapshot.plugins {
        entries.push(Entry::Separator);
        entries.push(Entry::Info(format!("{} · {}", card.title, card.summary)));
        for row in &card.rows {
            entries.push(Entry::Action {
                id: ActionId::Plugin {
                    action: row.action.clone(),
                    root: row.root.clone(),
                },
                label: format!("  {}", row.label),
                enabled: true,
            });
        }
        for group in &card.groups {
            entries.push(Entry::Submenu {
                about: ActionId::AlertGroup,
                label: format!("  {}", group.label),
                items: group.rows.iter().map(|row| Entry::Action {
                    id: ActionId::Plugin { action: row.action.clone(), root: row.root.clone() },
                    label: row.label.clone(), enabled: true,
                }).collect(),
            });
        }
        for action in &card.actions {
            // Only the actions a build knows how to name are drawn. An id from
            // a newer CDX is carried in the snapshot and simply not offered,
            // which is quieter than a menu row nobody can read.
            if let Some(label) = plugin_action_label(action) {
                entries.push(Entry::Action {
                    id: ActionId::Plugin {
                        action: action.clone(),
                        root: None,
                    },
                    label,
                    enabled: true,
                });
            }
        }
    }
    if !snapshot.terminal_candidates.is_empty() {
        entries.push(Entry::Submenu {
            about: ActionId::OpenTerminal,
            label: "Terminal for new sessions".into(),
            items: snapshot.terminal_candidates.iter().map(|candidate| Entry::Check {
                id: ActionId::SetTerminal(candidate.clone()), label: candidate.clone(), checked: snapshot.terminal.as_deref() == Some(candidate),
            }).collect(),
        });
    }
    if !alerts.is_empty() {
        entries.push(Entry::Separator);
        entries.push(Entry::Info("Alert groups".into()));
        // `recent` already supplies newest-first bounded history. Keeping the
        // first group occurrence preserves that order without a second clock or
        // read state; at eight events a tiny linear lookup is clearer than a map.
        let mut groups: Vec<(Option<&str>, Vec<&crate::events::Event>)> = Vec::new();
        for event in crate::events::recent(alerts) {
            let session = event.details.session.as_deref();
            if let Some((_, events)) = groups.iter_mut().find(|(key, _)| *key == session) {
                events.push(event);
            } else {
                groups.push((session, vec![event]));
            }
        }
        for (session, events) in groups {
            let label = match session {
                Some(name) => format!("  {name} ({})", events.len()),
                None => format!("  Other alerts ({})", events.len()),
            };
            let items = events
                .into_iter()
                .map(|event| {
                    let line = crate::events::alert_line(event);
                    match (&event.details.terminal_kind, &event.details.terminal_id, &event.details.session) {
                        (Some(kind), Some(id), _) => Entry::Action { id: ActionId::FocusTerminal { kind: kind.clone(), id: id.clone() }, label: line, enabled: true },
                        (_, _, Some(name)) => Entry::Action {
                            id: ActionId::Session(name.clone()),
                            label: line,
                            enabled: true,
                        },
                        _ => Entry::Info(line),
                    }
                })
                .collect();
            entries.push(Entry::Submenu {
                about: ActionId::AlertGroup,
                label,
                items,
            });
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
        provided(name, "codex", pct, freshness)
    }

    fn provided(name: &str, provider: &str, pct: Option<f64>, freshness: &str) -> Session {
        Session {
            name: name.into(),
            provider: provider.into(),
            // One window by default: the case where a provider reports only
            // what CDX could derive, which has to keep rendering as one figure.
            five_hour_pct: None,
            week_pct: None,
            available_pct: pct,
            freshness: freshness.into(),
            reset_at: None,
            reset_in: None,
            updated_ago: None,
        }
    }

    fn snapshot(sessions: Vec<Session>, refreshable: bool) -> Snapshot {
        Snapshot {
            events: Vec::new(),
            spool_path: None,
            alerts_enabled: true,
            icon_state: "low".into(),
            tooltip: "CDX · capacity low".into(),
            session_count: sessions.len() as u64,
            refreshable,
            update_hint: None,
            plugins: Vec::new(),
            terminal: None,
            terminal_candidates: Vec::new(),
            sessions,
        }
    }

    /// Every label the menu can show, submenu contents included: an action the
    /// user can only reach by opening a row is still an action the menu offers.
    fn labels(entries: &[Entry]) -> String {
        entries
            .iter()
            .map(|e| match e {
                Entry::Info(text) => text.clone(),
                Entry::Separator => "---".into(),
                Entry::Action { label, .. } | Entry::Check { label, .. } => label.clone(),
                Entry::Submenu { label, items, .. } => format!("{label}\n{}", labels(items)),
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// The sessions a menu lists, in order, by the name their row is about.
    fn listed(entries: &[Entry]) -> Vec<String> {
        entries
            .iter()
            .filter_map(|e| match e {
                Entry::Submenu {
                    about: ActionId::Session(name),
                    ..
                } => Some(name.clone()),
                _ => None,
            })
            .collect()
    }

    /// The actions inside one session's row.
    fn actions_for<'a>(entries: &'a [Entry], session: &str) -> &'a [Entry] {
        entries
            .iter()
            .find_map(|e| match e {
                Entry::Submenu {
                    about: ActionId::Session(name),
                    items,
                    ..
                } if name == session => Some(items.as_slice()),
                _ => None,
            })
            .expect("a row for that session")
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
        // The provider rides on the row, since there is no heading to carry it.
        assert!(text.contains("18%  work · codex"), "{text}");
        assert!(text.contains("—  side · codex · never reported"), "{text}");
    }

    /// The order the snapshot arrived in, kept exactly.
    ///
    /// Grouping used to reorder it: a provider took the rank of its most
    /// constrained session, so a healthy account could sit above the one that
    /// made the icon turn — which is the opposite of what the list is for.
    #[test]
    fn sessions_are_listed_once_each_in_snapshot_order() {
        let entries = build_with_alerts(
            &snapshot(
                vec![
                    provided("alpha", "claude", Some(4.0), "fresh"),
                    provided("beta", "codex", Some(30.0), "fresh"),
                    provided("gamma", "claude", Some(80.0), "fresh"),
                ],
                true,
            ),
            &[],
        );
        assert_eq!(listed(&entries), vec!["alpha", "beta", "gamma"]);
        // No heading survives, so nothing separates a provider from the next.
        let text = labels(&entries);
        assert!(!text.lines().any(|line| line.trim() == "claude"), "{text}");
        for provider in ["claude", "codex", "claude"] {
            assert!(text.contains(provider), "{text}");
        }
    }

    /// The case the request reported: a Codex session drops and overtakes the
    /// Claude ones between two draws. Under grouping plus a positional id, the
    /// row the user clicked and the session that opened were two different
    /// things. The name is the id now, so the two cannot come apart.
    #[test]
    fn a_session_overtaking_another_still_opens_the_row_that_was_clicked() {
        let before = build_with_alerts(
            &snapshot(
                vec![
                    provided("claude-main", "claude", Some(10.0), "fresh"),
                    provided("claude-side", "claude", Some(50.0), "fresh"),
                    provided("codex-work", "codex", Some(90.0), "fresh"),
                ],
                true,
            ),
            &[],
        );
        let after = build_with_alerts(
            &snapshot(
                vec![
                    provided("codex-work", "codex", Some(2.0), "fresh"),
                    provided("claude-main", "claude", Some(10.0), "fresh"),
                    provided("claude-side", "claude", Some(50.0), "fresh"),
                ],
                true,
            ),
            &[],
        );
        let bound = |entries: &[Entry], wanted: &str| {
            entries.iter().any(|e| match e {
                Entry::Submenu {
                    about: ActionId::Session(name),
                    label,
                    items,
                } => {
                    name == wanted
                        && label.contains(wanted)
                        // Every action inside names the same session as the row.
                        && items.iter().all(|item| match item {
                            Entry::Action {
                                id: ActionId::Session(inner) | ActionId::SessionConfig(inner),
                                ..
                            } => inner == wanted,
                            _ => false,
                        })
                }
                _ => false,
            })
        };
        for entries in [&before, &after] {
            for name in ["codex-work", "claude-main", "claude-side"] {
                assert!(bound(entries, name), "{name} is bound to its own row");
            }
        }
    }

    /// Opening is one named action now, not the only thing a click can mean.
    #[test]
    fn a_session_row_offers_opening_and_its_next_launch_settings() {
        let entries = build_with_alerts(
            &snapshot(vec![session("work", Some(50.0), "fresh")], true),
            &[],
        );
        let actions = actions_for(&entries, "work");
        assert_eq!(
            actions
                .iter()
                .map(|e| match e {
                    Entry::Action { id, label, enabled } => (id.clone(), label.clone(), *enabled),
                    other => panic!("unexpected entry in a session row: {other:?}"),
                })
                .collect::<Vec<_>>(),
            vec![
                (
                    ActionId::Session("work".into()),
                    "Open session".to_string(),
                    true
                ),
                (
                    ActionId::SessionConfig("work".into()),
                    "Launch settings (next launch)".to_string(),
                    true
                ),
            ]
        );
    }

    /// `req_043` AC3: nothing in the tray may read as changing a running
    /// assistant. The label is the whole guarantee, so it is asserted.
    #[test]
    fn the_settings_action_says_it_applies_to_the_next_launch() {
        let entries = build_with_alerts(
            &snapshot(vec![session("work", Some(50.0), "fresh")], true),
            &[],
        );
        let text = labels(&entries);
        assert!(text.contains("Launch settings (next launch)"), "{text}");
    }

    /// `req_043` AC4: no heading advertises an extension point that has nothing
    /// in it yet.
    #[test]
    fn no_empty_extension_placeholder_is_rendered() {
        let entries = build_with_alerts(
            &snapshot(vec![session("work", Some(50.0), "fresh")], true),
            &[],
        );
        let text = labels(&entries).to_lowercase();
        assert!(!text.contains("extension"), "{text}");
        assert!(!text.contains("logics"), "{text}");
    }

    fn card(rows: Vec<(&str, &str)>, actions: Vec<&str>) -> crate::snapshot::PluginCard {
        crate::snapshot::PluginCard {
            title: "Logics".into(),
            summary: "1 blocked · 2 in progress".into(),
            rows: rows
                .into_iter()
                .map(|(label, action)| crate::snapshot::PluginRow {
                    label: label.into(),
                    action: action.into(),
                    root: None,
                })
                .collect(),
            groups: Vec::new(),
            actions: actions.into_iter().map(str::to_string).collect(),
        }
    }

    /// `req_037` AC1: a card is a summary, at most two rows, and named actions.
    #[test]
    fn a_card_shows_its_summary_its_rows_and_the_actions_this_build_knows() {
        let mut snap = snapshot(vec![session("work", Some(50.0), "fresh")], true);
        snap.plugins = vec![card(
            vec![
                ("blocked: one", "logics.focus:task_010"),
                ("next: two", "logics.focus:task_020"),
            ],
            vec!["logics.open", "logics.refresh"],
        )];
        let entries = build_with_alerts(&snap, &[]);
        let text = labels(&entries);
        assert!(
            text.contains("Logics · 1 blocked · 2 in progress"),
            "{text}"
        );
        assert!(text.contains("blocked: one"), "{text}");
        assert!(text.contains("Open Logics"), "{text}");
        assert!(text.contains("Refresh Logics"), "{text}");

        let ids: Vec<String> = entries
            .iter()
            .filter_map(|e| match e {
                Entry::Action {
                    id: ActionId::Plugin { action, .. },
                    ..
                } => Some(action.clone()),
                _ => None,
            })
            .collect();
        assert_eq!(
            ids,
            vec![
                "logics.focus:task_010",
                "logics.focus:task_020",
                "logics.open",
                "logics.refresh"
            ]
        );
    }

    #[test]
    fn a_card_renders_repository_groups_as_bounded_submenus() {
        let mut snap = snapshot(vec![], true);
        let mut grouped = card(vec![], vec!["logics.open"]);
        grouped.groups = vec![crate::snapshot::PluginGroup {
            label: "project".into(),
            rows: vec![crate::snapshot::PluginRow {
                label: "next: Ship it".into(),
                action: "logics.focus:task_1".into(),
                root: Some("/repo/project".into()),
            }],
        }];
        snap.plugins = vec![grouped];
        let entries = build_with_alerts(&snap, &[]);
        let group = entries.iter().find_map(|entry| match entry {
            Entry::Submenu { label, items, .. } if label.contains("project") => Some(items),
            _ => None,
        }).expect("repository submenu");
        assert!(matches!(&group[0], Entry::Action { id: ActionId::Plugin { action, root }, .. } if action == "logics.focus:task_1" && root.as_deref() == Some("/repo/project")));
    }

    /// An id from a newer CDX is carried and simply not offered: a menu row
    /// nobody can read is worse than one that is absent.
    #[test]
    fn an_action_this_build_has_no_name_for_is_not_drawn() {
        let mut snap = snapshot(vec![], true);
        snap.plugins = vec![card(vec![], vec!["logics.somethingnew"])];
        let entries = build_with_alerts(&snap, &[]);
        assert!(!entries.iter().any(|e| matches!(
            e,
            Entry::Action {
                id: ActionId::Plugin { .. },
                ..
            }
        )));
        // The card itself still appears: the summary is the part that matters.
        assert!(
            labels(&entries).contains("Logics · 1 blocked"),
            "{}",
            labels(&entries)
        );
    }

    /// No enabled integration is the normal case, and it adds nothing at all.
    #[test]
    fn no_card_means_no_section() {
        let entries = build_with_alerts(
            &snapshot(vec![session("w", Some(50.0), "fresh")], true),
            &[],
        );
        assert!(!labels(&entries).to_lowercase().contains("logics"));
    }

    /// `req_046` AC4: a week almost spent must not hide behind a five-hour
    /// window that has just reset, which is exactly what one figure did.
    #[test]
    fn both_windows_are_named_on_the_row() {
        let mut session = session("work", Some(12.0), "fresh");
        session.five_hour_pct = Some(80.0);
        session.week_pct = Some(12.0);
        assert_eq!(
            windows(&session),
            vec![("5h", Some(80.0)), ("wk", Some(12.0))]
        );
        let line = session_line(&session);
        assert!(line.contains("5h 80% · wk 12%"), "{line}");
        // The leading gauge stays on the window that runs out first, so the
        // column the eye scans means one thing all the way down.
        assert!(line.trim_start().starts_with(&gauge(Some(12.0))), "{line}");
    }

    #[test]
    fn a_single_window_is_named_and_implies_no_missing_second() {
        let mut only_week = session("work", Some(30.0), "fresh");
        only_week.week_pct = Some(30.0);
        assert_eq!(windows(&only_week), vec![("wk", Some(30.0))]);
        assert!(session_line(&only_week).contains("wk 30%"));
    }

    /// A provider that meters neither window still has a figure CDX derived,
    /// and an empty row would be a regression for the sake of a distinction
    /// that does not apply.
    #[test]
    fn a_session_with_no_named_window_still_shows_its_figure() {
        let plain = session("work", Some(45.0), "fresh");
        assert_eq!(windows(&plain), vec![("", Some(45.0))]);
        assert!(session_line(&plain).contains("45%"));
        let never = session("side", None, "unknown");
        assert!(session_line(&never).contains("—"));
    }

    /// `req_046` AC1 and AC2: the drawn row has to say the two things a text
    /// row says, in the same words, or macOS is the one platform that draws and
    /// the one platform that does not tell you whether to trust the figure.
    #[test]
    fn the_drawn_row_says_how_old_the_figure_is_and_when_it_resets() {
        let mut stale = session("work", Some(40.0), "stale");
        stale.updated_ago = Some("3h ago".into());
        stale.reset_in = Some("in 5h".into());
        assert_eq!(row_detail(&stale), "stale 3h ago · ↻ in 5h");
        // The same words the text row uses, not a second phrasing.
        let line = session_line(&stale);
        assert!(line.contains("stale 3h ago"), "{line}");
        assert!(line.contains("↻ in 5h"), "{line}");
    }

    /// A current figure states its age rather than nothing: an empty second
    /// line reads as missing data, where an unadorned text row does not.
    #[test]
    fn a_current_figure_still_says_when_it_was_taken() {
        let mut fresh = session("work", Some(40.0), "fresh");
        fresh.updated_ago = Some("2m ago".into());
        assert_eq!(row_detail(&fresh), "2m ago");
        // And the text row still says nothing, because there is nothing wrong.
        assert!(!session_line(&fresh).contains("2m ago"));
    }

    #[test]
    fn the_drawn_row_names_the_states_a_refresh_cannot_fix() {
        let running = session("work", Some(40.0), "auth_locked");
        assert_eq!(row_detail(&running), "running");
        let never = session("side", None, "unknown");
        assert_eq!(row_detail(&never), "never reported");
        let mut bare = session("bare", Some(10.0), "fresh");
        bare.updated_ago = None;
        assert_eq!(row_detail(&bare), "just now");
    }

    #[test]
    fn an_absolute_reset_reaches_the_drawn_row_when_that_is_all_there_is() {
        let mut stamped = session("work", Some(40.0), "fresh");
        stamped.updated_ago = Some("1m ago".into());
        stamped.reset_at = Some("Aug 18 03:23".into());
        assert_eq!(row_detail(&stamped), "1m ago · ↻ Aug 18 03:23");
    }

    /// `req_039` AC5: the alert is where the user already is when they want
    /// that session, so it opens it rather than sending them back up the menu.
    #[test]
    fn a_structured_alert_opens_the_session_it_names() {
        let alert = crate::events::Event {
            id: "a".into(),
            kind: "attention".into(),
            title: "✓ work".into(),
            message: "repo · needs your attention".into(),
            details: crate::events::Details {
                session: Some("work".into()),
                project: Some("repo".into()),
                event: Some("permissionrequest".into()),
                tool: Some("Bash".into()),
                ..Default::default()
            },
        };
        let entries = build_with_alerts(&snapshot(vec![], true), &[alert]);
        let clicked = entries.iter().find_map(|e| match e {
            Entry::Submenu { label, items, .. } if label == "  work (1)" => {
                items.iter().find_map(|e| match e {
                    Entry::Action {
                        id: ActionId::Session(name),
                        label,
                        ..
                    } => Some((name.clone(), label.clone())),
                    _ => None,
                })
            }
            _ => None,
        });
        assert_eq!(
            clicked,
            Some(("work".into(), "! work · repo · permission (Bash)".into()))
        );
    }

    /// An alert from a CDX older than the structured fields has no session to
    /// open, and guessing one out of the sentence is exactly what this work
    /// removed. It stays text.
    #[test]
    fn an_alert_without_fields_stays_text_rather_than_guessing() {
        let alert = crate::events::Event {
            id: "a".into(),
            kind: "complete".into(),
            title: "✓ work".into(),
            message: "repo · turn complete".into(),
            details: crate::events::Details::default(),
        };
        let entries = build_with_alerts(&snapshot(vec![], true), &[alert]);
        assert!(!entries.iter().any(|e| matches!(
            e,
            Entry::Action {
                id: ActionId::Session(_),
                ..
            }
        )));
        assert!(labels(&entries).contains("✓ work — repo · turn complete"));
    }

    #[test]
    fn alerts_group_by_session_in_newest_group_order() {
        let event = |id: &str, session: &str| crate::events::Event {
            id: id.into(),
            kind: "complete".into(),
            title: id.into(),
            message: "done".into(),
            details: crate::events::Details {
                session: Some(session.into()),
                ..Default::default()
            },
        };
        let entries = build_with_alerts(
            &snapshot(vec![], true),
            &[
                event("old", "alpha"),
                event("middle", "beta"),
                event("new", "alpha"),
            ],
        );
        let groups = entries
            .iter()
            .filter_map(|entry| match entry {
                Entry::Submenu {
                    about: ActionId::AlertGroup,
                    label,
                    items,
                } => Some((label.as_str(), items.len())),
                _ => None,
            })
            .collect::<Vec<_>>();
        assert_eq!(groups, vec![("  alpha (2)", 2), ("  beta (1)", 1)]);
    }

    /// `req_043` AC5: an action that cannot run says why instead of vanishing.
    #[test]
    fn an_unavailable_action_is_disabled_and_carries_its_reason() {
        let entries = session_entries_from(vec![SessionAction {
            id: ActionId::SessionConfig("work".into()),
            label: "Launch settings (next launch)".into(),
            availability: Availability::Unavailable("this CDX is too old".into()),
        }]);
        match &entries[0] {
            Entry::Action { label, enabled, .. } => {
                assert!(!enabled);
                assert!(label.contains("this CDX is too old"), "{label}");
            }
            other => panic!("expected a disabled action, got {other:?}"),
        }
    }

    #[test]
    fn a_stale_row_says_how_stale() {
        // "stale" says the figure is old; the age says how old, which is the
        // part a reader can act on without opening anything else.
        let mut aged = session("work", Some(40.0), "stale");
        aged.updated_ago = Some("3h ago".into());
        let entries = build_with_alerts(&snapshot(vec![aged], true), &[]);
        assert!(
            labels(&entries).contains("stale 3h ago"),
            "{}",
            labels(&entries)
        );
    }

    #[test]
    fn the_reset_is_a_distance_when_cdx_computed_one() {
        let mut soon = session("work", Some(40.0), "fresh");
        soon.reset_at = Some("Aug 18 03:23".into());
        soon.reset_in = Some("in 5h".into());
        let text = labels(&build_with_alerts(&snapshot(vec![soon], true), &[]));
        assert!(text.contains("↻ in 5h"), "{text}");
        // Never both: they say the same thing at different lengths.
        assert!(!text.contains("Aug 18"), "{text}");
    }

    #[test]
    fn an_older_cdx_still_gets_its_absolute_reset() {
        let mut stamped = session("work", Some(40.0), "fresh");
        stamped.reset_at = Some("Aug 18 03:23".into());
        let text = labels(&build_with_alerts(&snapshot(vec![stamped], true), &[]));
        assert!(text.contains("↻ Aug 18 03:23"), "{text}");
    }

    #[test]
    fn a_running_session_says_refresh_cannot_help() {
        let entries = build_with_alerts(
            &snapshot(vec![session("work", Some(40.0), "auth_locked")], false),
            &[],
        );
        let text = labels(&entries);
        assert!(text.contains("40%  work · codex · running"), "{text}");
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
        assert!(quits(build_unavailable(&Unavailable::CdxTooOld(
            "wsl.exe -d Ubuntu -- cdx".into()
        ))));
    }

    #[test]
    fn an_unavailable_menu_names_the_boundary_and_invents_no_quota() {
        let entries = build_unavailable(&Unavailable::CdxTooOld("wsl.exe -d Ubuntu -- cdx".into()));
        let text = labels(&entries);
        assert!(text.contains("unavailable"), "{text}");
        // It names the command that answered: on WSL the CDX the companion
        // reaches is frequently not the one the user's terminal resolves.
        assert!(text.contains("wsl.exe -d Ubuntu -- cdx"), "{text}");
        assert!(text.contains("CDX_TRAY_CDX"), "{text}");
        assert!(
            !text.contains('%'),
            "no figure may appear when nothing is known: {text}"
        );
    }
}
