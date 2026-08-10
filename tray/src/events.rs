//! Agent alerts, collected from CDX and acknowledged once shown.
//!
//! The companion never opens the spool. It asks CDX over the same transport it
//! already uses for status, because on a Windows host serving CDX from WSL the
//! spool is in the Linux filesystem and the tray is not. One transport, one set
//! of assumptions, and no path translation anywhere.
//!
//! Every failure here is silence, never a crash: an alert that cannot be
//! collected is one CDX still delivered directly, because the heartbeat this
//! module writes is what gave the tray ownership in the first place. Stop
//! beating and CDX takes the alerts back.

use std::process::Command;

use crate::snapshot::Transport;

/// How many past alerts the menu keeps. Enough to answer "what did I miss",
/// short enough that the menu stays a menu rather than a log.
pub const HISTORY_LIMIT: usize = 8;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Event {
    pub id: String,
    pub kind: String,
    pub title: String,
    pub message: String,
}

fn run(mut command: Command) -> Option<String> {
    let output = command.output().ok()?;
    if !output.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// Mark alerts shown. Called only after they have been rendered, so a companion
/// that dies mid-draw shows them again rather than losing them: a repeat is a
/// smaller failure than a notification the user never sees.
pub fn acknowledge(transport: &Transport, ids: &[String]) {
    if ids.is_empty() {
        return;
    }
    let mut args = vec!["tray", "ack"];
    args.extend(ids.iter().map(String::as_str));
    args.push("--json");
    let _ = run(transport.command_for(&args));
}

/// The events array out of whatever carried it.
///
/// Tolerant in the same way the snapshot reader is: a payload from a newer CDX
/// may carry fields this build has never heard of, and refusing it would turn a
/// version difference into silence.
pub fn parse_array(value: Option<&serde_json::Value>) -> Vec<Event> {
    let items = match value.and_then(|v| v.as_array()) {
        Some(items) => items,
        None => return Vec::new(),
    };
    items
        .iter()
        .filter_map(|item| {
            let id = item.get("id")?.as_str()?.to_string();
            Some(Event {
                id,
                kind: item
                    .get("kind")
                    .and_then(|v| v.as_str())
                    .unwrap_or("complete")
                    .to_string(),
                title: item
                    .get("title")
                    .and_then(|v| v.as_str())
                    .unwrap_or("CDX")
                    .to_string(),
                message: item
                    .get("message")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            })
        })
        .collect()
}

/// The menu's recent-alert section: newest first, bounded.
pub fn history_lines(history: &[Event]) -> Vec<String> {
    history
        .iter()
        .rev()
        .take(HISTORY_LIMIT)
        .map(|event| {
            let mark = if event.kind == "attention" { "!" } else { "·" };
            format!("{mark} {} — {}", event.title, event.message)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The tests speak in payloads; the loop reads an already-parsed value.
    fn parse(payload: &str) -> Vec<Event> {
        let value: serde_json::Value = match serde_json::from_str(payload) {
            Ok(value) => value,
            Err(_) => return Vec::new(),
        };
        parse_array(value.get("events"))
    }

    #[test]
    fn a_payload_yields_its_events_in_order() {
        let events = parse(
            r#"{"ok":true,"events":[
                {"id":"a","kind":"complete","title":"✓ work","message":"repo · turn complete"},
                {"id":"b","kind":"attention","title":"✓ main","message":"repo · needs your attention"}
            ]}"#,
        );
        assert_eq!(events.len(), 2);
        assert_eq!(events[0].id, "a");
        assert_eq!(events[1].kind, "attention");
    }

    #[test]
    fn an_entry_without_an_id_is_dropped_rather_than_guessed() {
        // Acknowledging needs an id. An event without one could be shown but
        // never acknowledged, so it would reappear on every poll forever.
        let events = parse(r#"{"events":[{"kind":"complete","title":"t","message":"m"}]}"#);
        assert!(events.is_empty());
    }

    #[test]
    fn a_foreign_or_broken_payload_is_no_events_not_a_crash() {
        for payload in ["", "not json", "{}", r#"{"events":"nope"}"#] {
            assert!(parse(payload).is_empty(), "{payload}");
        }
    }

    #[test]
    fn missing_optional_fields_fall_back_rather_than_dropping_the_alert() {
        let events = parse(r#"{"events":[{"id":"a"}]}"#);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].kind, "complete");
        assert_eq!(events[0].title, "CDX");
    }

    #[test]
    fn the_history_is_newest_first_and_bounded() {
        let history: Vec<Event> = (0..HISTORY_LIMIT + 4)
            .map(|index| Event {
                id: index.to_string(),
                kind: "complete".into(),
                title: format!("✓ s{index}"),
                message: "m".into(),
            })
            .collect();
        let lines = history_lines(&history);
        assert_eq!(lines.len(), HISTORY_LIMIT);
        assert!(
            lines[0].contains(&format!("s{}", HISTORY_LIMIT + 3)),
            "{lines:?}"
        );
    }

    #[test]
    fn attention_is_marked_differently_from_completion() {
        let lines = history_lines(&[Event {
            id: "a".into(),
            kind: "attention".into(),
            title: "✓ work".into(),
            message: "repo · needs your attention".into(),
        }]);
        assert!(lines[0].starts_with('!'), "{lines:?}");
    }
}
