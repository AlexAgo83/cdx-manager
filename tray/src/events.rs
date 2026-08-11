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
    /// The rendered sentence CDX composed. Kept even when the fields below are
    /// present: it is what an event from an older CDX has, and what a malformed
    /// `details` falls back to.
    pub title: String,
    pub message: String,
    pub details: Details,
}

/// The event as fields rather than prose.
///
/// Everything is optional because everything can be absent: an older CDX sends
/// none of it, and a newer one omits what a given provider did not supply. A
/// missing field is never an error — it is a line that says slightly less.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Details {
    /// The cdx session this belongs to. What makes an alert clickable: with it
    /// the menu can offer to open the session, without it the row is text.
    pub session: Option<String>,
    pub project: Option<String>,
    /// The provider hook that fired, normalised: `stop`, `permissionrequest`,
    /// `notification`.
    pub event: Option<String>,
    pub tool: Option<String>,
    /// The provider's error class on a failed turn, from its closed vocabulary.
    pub error_type: Option<String>,
    pub reason: Option<String>,
    pub preview: Option<String>,
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

/// Perform one plugin card action, by handing its id back to CDX.
///
/// The companion never interprets the id and never builds a command from it:
/// CDX matches it against the fixed vocabulary it published and refuses
/// anything else. That is the whole reason a card can offer an action at all
/// without an integration gaining a way to run something on this machine.
pub fn run_plugin_action(transport: &Transport, action: &str) {
    let _ = run(transport.command_for(&["tray", "plugin", "run", action, "--json"]));
}

/// Mute or unmute agent alerts, through CDX rather than in the companion.
pub fn set_alerts(transport: &Transport, enabled: bool) {
    let mode = if enabled { "on" } else { "off" };
    let _ = run(transport.command_for(&["tray", "alerts", mode, "--json"]));
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
            let details = item.get("details");
            let field = |name: &str| {
                details
                    .and_then(|d| d.get(name))
                    .and_then(|v| v.as_str())
                    .filter(|text| !text.is_empty())
                    .map(str::to_string)
            };
            Some(Event {
                id,
                details: Details {
                    session: field("session"),
                    project: field("project"),
                    event: field("event"),
                    tool: field("tool"),
                    error_type: field("error_type"),
                    reason: field("reason"),
                    preview: field("preview"),
                },
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

/// The alerts the menu shows: newest first, bounded.
///
/// The order and the bound live here rather than in the menu, so the count
/// beside the icon and the list under it can never disagree about how many
/// there are.
pub fn recent(history: &[Event]) -> impl Iterator<Item = &Event> {
    history.iter().rev().take(HISTORY_LIMIT)
}

/// One alert as the menu shows it.
///
/// Composed from the fields when they are there, and from the sentence CDX
/// rendered when they are not. Nothing here parses that sentence — an older
/// event is shown as it arrived rather than picked apart, because a display
/// string is a presentation, not a contract.
pub fn alert_line(event: &Event) -> String {
    // Three shapes, three marks. A failed turn is not an attention request and
    // certainly not a completion: it is the one a user scanning the list has to
    // be able to find without reading. A kind this build does not know falls
    // back to the neutral mark rather than being hidden.
    let mark = match event.kind.as_str() {
        "attention" => "!",
        "failed" => "✕",
        _ => "·",
    };
    let Some(session) = &event.details.session else {
        return format!("{mark} {} — {}", event.title, event.message);
    };
    let mut line = format!("{mark} {session}");
    if let Some(project) = &event.details.project {
        line.push_str(&format!(" · {project}"));
    }
    line.push_str(match event.details.event.as_deref() {
        Some("permissionrequest") => " · permission",
        Some("stop") => " · done",
        Some("stopfailure") => " · failed",
        Some("notification") => " · waiting",
        // An event this build has not heard of still gets a line, because a
        // newer CDX inventing one must not make its alerts invisible.
        Some(_) | None => " · alert",
    });
    // The tool for a permission request, the error class for a failure: the one
    // word that says which of its kind this is.
    if let Some(tool) = event
        .details
        .tool
        .as_ref()
        .or(event.details.error_type.as_ref())
    {
        line.push_str(&format!(" ({tool})"));
    }
    // The reason and the preview are the same slot: an alert has one thing to
    // quote, and a permission request quotes what it wants to do rather than
    // what was said before it.
    if let Some(text) = event
        .details
        .reason
        .as_ref()
        .or(event.details.preview.as_ref())
    {
        line.push_str(&format!(" — {text}"));
    }
    line
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
                details: Details::default(),
            })
            .collect();
        let lines: Vec<String> = recent(&history).map(alert_line).collect();
        assert_eq!(lines.len(), HISTORY_LIMIT);
        assert!(
            lines[0].contains(&format!("s{}", HISTORY_LIMIT + 3)),
            "{lines:?}"
        );
    }

    /// An event from a CDX older than the fields still reads exactly as it did:
    /// the sentence it composed is shown, and nothing tries to take it apart.
    #[test]
    fn an_event_without_fields_falls_back_to_the_rendered_sentence() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"complete","title":"✓ work","message":"repo · turn complete"}]}"#,
        );
        assert_eq!(events[0].details, Details::default());
        assert_eq!(alert_line(&events[0]), "· ✓ work — repo · turn complete");
    }

    #[test]
    fn a_structured_permission_alert_names_the_session_and_the_tool() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"attention","title":"✓ work","message":"repo · needs your attention (Bash)",
                "details":{"session":"work","project":"repo","event":"permissionrequest","tool":"Bash"}}]}"#,
        );
        assert_eq!(events[0].details.session.as_deref(), Some("work"));
        assert_eq!(alert_line(&events[0]), "! work · repo · permission (Bash)");
    }

    #[test]
    fn a_structured_completion_quotes_its_preview_when_there_is_one() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"complete","title":"✓ work","message":"repo · turn complete",
                "details":{"session":"work","project":"repo","event":"stop","preview":"All done"}}]}"#,
        );
        assert_eq!(alert_line(&events[0]), "· work · repo · done — All done");
    }

    /// A field this build has never heard of must not make the alert vanish.
    #[test]
    fn a_failed_turn_is_marked_apart_from_both_completion_and_attention() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"failed","title":"✕ work","message":"repo · turn failed (rate_limit)",
                "details":{"session":"work","project":"repo","event":"stopfailure","error_type":"rate_limit"}}]}"#,
        );
        assert_eq!(
            alert_line(&events[0]),
            "✕ work · repo · failed (rate_limit)"
        );
    }

    /// A companion older than the failure kind shows the neutral mark, and the
    /// sentence CDX rendered still says the turn failed.
    #[test]
    fn an_unknown_kind_falls_back_to_the_neutral_mark() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"somethingnew","title":"✕ work","message":"repo · turn failed"}]}"#,
        );
        assert!(alert_line(&events[0]).starts_with('·'));
        assert!(alert_line(&events[0]).contains("turn failed"));
    }

    #[test]
    fn an_unknown_event_name_still_produces_a_line() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"complete","title":"t","message":"m",
                "details":{"session":"work","event":"somethingnew"}}]}"#,
        );
        assert_eq!(alert_line(&events[0]), "· work · alert");
    }

    /// A details block that is not an object is the malformed case, and it has
    /// to degrade to the sentence rather than drop the alert.
    #[test]
    fn a_malformed_details_block_leaves_the_sentence_standing() {
        let events = parse(
            r#"{"events":[{"id":"a","kind":"complete","title":"✓ work","message":"repo · turn complete","details":"nonsense"}]}"#,
        );
        assert_eq!(events.len(), 1);
        assert_eq!(alert_line(&events[0]), "· ✓ work — repo · turn complete");
    }

    #[test]
    fn attention_is_marked_differently_from_completion() {
        let lines: Vec<String> = recent(&[Event {
            id: "a".into(),
            kind: "attention".into(),
            title: "✓ work".into(),
            message: "repo · needs your attention".into(),
            details: Details::default(),
        }])
        .map(alert_line)
        .collect();
        assert!(lines[0].starts_with('!'), "{lines:?}");
    }
}
