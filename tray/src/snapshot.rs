//! Getting the snapshot from `cdx`, and what it contains.
//!
//! Per `adr_005` the transport is `cdx` itself, invoked as a child process, and
//! the snapshot arrives on stdout. There is no status file, no socket, and no
//! provider call from here. Across the WSL boundary the same command is wrapped
//! in `wsl.exe`, because WSL localhost is directional in NAT mode and mirrored
//! mode cannot be assumed on a user's machine.

use std::process::Command;

use serde_json::Value;

pub const SCHEMA_NAME: &str = "cdx.tray.snapshot";
/// The snapshot major this build understands. A newer major is readable, not
/// fatal: CDX and the companion update separately and drift is the normal
/// state, so we render what we know and say an update is available.
pub const SCHEMA_MAJOR: u64 = 1;

/// One configuration value, trimmed and emptied-to-None.
///
/// The trimming is not cosmetic. In `cmd.exe`, `set VAR=1 && next-command`
/// stores `"1 "` with the trailing space, so an untrimmed comparison silently
/// falls back to the native transport on the exact platform where WSL matters.
/// Found by running the companion on a real Windows host.
fn setting(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

/// How to reach `cdx`. On a Windows host serving CDX inside WSL the command is
/// the same, wrapped in an interop call.
pub enum Transport {
    Native,
    Wsl { distro: Option<String> },
}

impl Transport {
    /// `CDX_TRAY_WSL=1` selects interop, `CDX_TRAY_WSL_DISTRO` names a
    /// distribution. Environment rather than config file for now: item_085
    /// owns the real resolution, including the default-distribution rules.
    pub fn from_env() -> Self {
        match setting("CDX_TRAY_WSL").as_deref() {
            Some("1") | Some("true") => Transport::Wsl {
                distro: setting("CDX_TRAY_WSL_DISTRO"),
            },
            _ => Transport::Native,
        }
    }

    pub fn is_wsl(&self) -> bool {
        matches!(self, Transport::Wsl { .. })
    }

    /// Which `cdx` to run. `wsl.exe -- cdx` resolves against WSL's
    /// non-interactive PATH, which often omits `~/.local/bin`, so an absolute
    /// path has to be expressible. Measured on a real host before adding this.
    pub fn cdx_command() -> String {
        setting("CDX_TRAY_CDX").unwrap_or_else(|| "cdx".to_string())
    }

    fn command(&self) -> Command {
        self.command_for(&["tray", "status", "--json", "--beat"])
    }

    /// The same read without claiming ownership of alerts. `--print` uses this:
    /// heartbeating from a process about to exit would tell `cdx notify` a tray
    /// is listening when none is.
    fn read_only_command(&self) -> Command {
        self.command_for(&["tray", "status", "--json"])
    }

    /// Any `cdx` subcommand, over whichever transport this companion uses.
    ///
    /// Events travel the same way status does, on purpose: on a Windows host
    /// serving CDX from WSL the spool is in the Linux filesystem, so anything
    /// that read it directly would need a path translation or a share. One
    /// transport, one set of assumptions.
    pub fn command_for(&self, args: &[&str]) -> Command {
        let cdx = Self::cdx_command();
        match self {
            Transport::Native => {
                let mut cmd = Command::new(cdx);
                cmd.args(args);
                cmd
            }
            Transport::Wsl { distro } => {
                let mut cmd = Command::new("wsl.exe");
                if let Some(name) = distro {
                    cmd.args(["-d", name]);
                }
                cmd.args(["--", &cdx]);
                cmd.args(args);
                cmd
            }
        }
    }

    pub fn describe(&self) -> String {
        match self {
            Transport::Native => format!("{} tray status --json", Self::cdx_command()),
            Transport::Wsl { distro: Some(d) } => {
                format!(
                    "wsl.exe -d {d} -- {} tray status --json",
                    Self::cdx_command()
                )
            }
            Transport::Wsl { distro: None } => {
                format!("wsl.exe -- {} tray status --json", Self::cdx_command())
            }
        }
    }
}

/// Why the companion has nothing to show. Every variant is a state the tray
/// must be able to render honestly; none of them may become a fabricated quota.
#[derive(Debug, PartialEq, Eq)]
pub enum Unavailable {
    CdxNotFound(String),
    /// A configured WSL distribution that does not exist. Distinct from a
    /// missing CDX: the distribution is the thing that is wrong, and reporting
    /// "CDX not found" would send the user looking in the wrong place.
    WslDistro(String),
    /// CDX is installed but predates `cdx tray`. This is version drift in the
    /// other direction from an unknown snapshot major, and it is what a user
    /// hits after installing the companion without updating CDX.
    CdxTooOld,
    CdxFailed {
        code: Option<i32>,
        stderr: String,
    },
    NotJson,
    NotASnapshot,
}

impl std::fmt::Display for Unavailable {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Unavailable::CdxNotFound(how) => {
                write!(f, "cannot run `{how}`: CDX not found on this host")
            }
            Unavailable::WslDistro(problem) => write!(f, "{problem}"),
            Unavailable::CdxTooOld => write!(
                f,
                "this CDX does not have `cdx tray`. Update CDX to use the tray companion."
            ),
            Unavailable::CdxFailed { code, stderr } => {
                let code = code
                    .map(|c| c.to_string())
                    .unwrap_or_else(|| "signal".into());
                write!(f, "cdx exited with {code}: {}", stderr.trim())
            }
            Unavailable::NotJson => write!(f, "cdx returned output that is not JSON"),
            Unavailable::NotASnapshot => write!(f, "cdx returned JSON that is not a {SCHEMA_NAME}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Session {
    pub name: String,
    pub provider: String,
    /// The window that runs out first, which is what the icon and the ordering
    /// follow. CDX computes it as the minimum of the two below.
    pub available_pct: Option<f64>,
    /// The five-hour and weekly windows, when the provider reports them.
    ///
    /// Both providers publish both, and CDX has been sending them since the
    /// snapshot existed — the companion simply read neither, so a nearly spent
    /// week was invisible behind a five-hour window that had just reset.
    pub five_hour_pct: Option<f64>,
    pub week_pct: Option<f64>,
    pub freshness: String,
    pub reset_at: Option<String>,
    /// The reset as a distance rather than a stamp — "in 5h" instead of
    /// "Aug 18 03:23". Shorter by half, and it answers the question the reader
    /// actually has without making them subtract.
    pub reset_in: Option<String>,
    /// How long since this figure was reported, or `None` when it never was.
    pub updated_ago: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Snapshot {
    pub icon_state: String,
    /// What the closed icon may say on hover. Built by CDX so the companion
    /// cannot accidentally compose something the privacy rule forbids.
    pub tooltip: String,
    /// Alerts CDX is holding, delivered with the snapshot rather than fetched
    /// separately: across WSL each extra call is another `wsl.exe` crossing.
    pub events: Vec<crate::events::Event>,
    /// Where the alert spool lives, so a companion sharing the filesystem can
    /// notice an alert between polls instead of waiting for the next one.
    pub spool_path: Option<String>,
    /// Whether an alert may raise a banner. Read from CDX rather than kept by
    /// the companion: the hook is what obeys it, and the hook is not the tray.
    pub alerts_enabled: bool,
    pub session_count: u64,
    pub refreshable: bool,
    /// Set when the snapshot is newer than this build understands.
    pub update_hint: Option<String>,
    pub sessions: Vec<Session>,
    /// Cards from integrations the user enabled in CDX. Empty is the normal
    /// case and an older CDX sends none at all.
    pub plugins: Vec<PluginCard>,
    /// Which terminal a session row should open, or `None` for this platform's
    /// own. CDX validates it as an application name; the companion never builds
    /// a command out of it, only hands it to the platform's launcher.
    pub terminal: Option<String>,
}

/// One integration's card, already bounded by CDX.
///
/// The companion re-reads the bounds anyway — two rows, and an action id it
/// hands straight back to CDX. Not distrust of CDX so much as the same rule
/// everywhere else here: what arrives over the transport is checked, because a
/// version mismatch is a normal state and a crash is not.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PluginCard {
    pub title: String,
    pub summary: String,
    pub rows: Vec<PluginRow>,
    /// The card-wide actions, in the order CDX listed them.
    pub actions: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PluginRow {
    pub label: String,
    pub action: String,
}

/// The most rows a card may contribute, mirroring CDX's own bound. A menu that
/// grew with an integration would stop being a quota menu.
const MAX_PLUGIN_ROWS: usize = 2;

pub fn fetch(transport: &Transport) -> Result<Snapshot, Unavailable> {
    fetch_with(transport, true)
}

/// The same poll without writing a heartbeat, for callers that will not stay
/// around to show what they collect.
pub fn fetch_read_only(transport: &Transport) -> Result<Snapshot, Unavailable> {
    fetch_with(transport, false)
}

fn fetch_with(transport: &Transport, beat: bool) -> Result<Snapshot, Unavailable> {
    // Check the distribution before blaming CDX for being absent from it.
    if let Transport::Wsl { distro: Some(name) } = transport {
        let resolution = crate::wsl::resolve(Some(name), crate::wsl::installed());
        if let Some(problem) = resolution.problem() {
            return Err(Unavailable::WslDistro(problem));
        }
    }
    let mut command = if beat {
        transport.command()
    } else {
        transport.read_only_command()
    };
    let output = command
        .output()
        .map_err(|_| Unavailable::CdxNotFound(transport.describe()))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        if error_code(&stderr).as_deref() == Some("unknown_command") {
            return Err(Unavailable::CdxTooOld);
        }
        return Err(Unavailable::CdxFailed {
            code: output.status.code(),
            stderr,
        });
    }
    let payload: Value =
        serde_json::from_slice(&output.stdout).map_err(|_| Unavailable::NotJson)?;
    read_snapshot(&payload)
}

/// CDX publishes machine-readable error codes on failure. Reading the code
/// rather than matching the message keeps this working when the wording changes.
fn error_code(stderr: &str) -> Option<String> {
    serde_json::from_str::<Value>(stderr)
        .ok()?
        .get("error")?
        .get("code")?
        .as_str()
        .map(str::to_string)
}

/// A card, or nothing. A malformed one is dropped rather than drawn empty: a
/// menu section with a title and no meaning is worse than no section.
fn plugin_card_from(value: &Value) -> Option<PluginCard> {
    let text = |key: &str| {
        value
            .get(key)
            .and_then(Value::as_str)
            .filter(|v| !v.is_empty())
            .map(str::to_string)
    };
    let action_of = |item: &Value| {
        item.get("action")
            .and_then(Value::as_str)
            .filter(|a| !a.is_empty())
            .map(str::to_string)
    };
    Some(PluginCard {
        title: text("title")?,
        summary: text("summary")?,
        rows: value
            .get("rows")
            .and_then(Value::as_array)
            .map(|rows| {
                rows.iter()
                    .filter_map(|row| {
                        Some(PluginRow {
                            label: row
                                .get("label")
                                .and_then(Value::as_str)
                                .filter(|l| !l.is_empty())?
                                .to_string(),
                            action: action_of(row)?,
                        })
                    })
                    .take(MAX_PLUGIN_ROWS)
                    .collect()
            })
            .unwrap_or_default(),
        actions: value
            .get("actions")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(|item| item.as_str().filter(|a| !a.is_empty()).map(str::to_string))
                    .take(MAX_PLUGIN_ROWS)
                    .collect()
            })
            .unwrap_or_default(),
    })
}

fn optional_pct(value: &Value, key: &str) -> Option<f64> {
    value.get(key).and_then(Value::as_f64)
}

fn session_from(value: &Value) -> Session {
    Session {
        name: value
            .get("name")
            .and_then(Value::as_str)
            .unwrap_or("?")
            .to_string(),
        provider: value
            .get("provider")
            .and_then(Value::as_str)
            .unwrap_or("-")
            .to_string(),
        available_pct: optional_pct(value, "available_pct"),
        five_hour_pct: optional_pct(value, "remaining_5h_pct"),
        week_pct: optional_pct(value, "remaining_week_pct"),
        freshness: value
            .get("freshness")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
        reset_at: value
            .get("reset_at")
            .and_then(Value::as_str)
            .map(str::to_string),
        // Absent from an older CDX, which simply means the row falls back to
        // the absolute stamp it already carried.
        reset_in: value
            .get("reset_in")
            .and_then(Value::as_str)
            .filter(|v| !v.is_empty() && *v != "-")
            .map(str::to_string),
        updated_ago: value
            .get("updated_ago")
            .and_then(Value::as_str)
            .map(str::to_string),
    }
}

/// Mirrors `read_snapshot` in `src/tray_contract.py`: an unknown major keeps
/// every field this reader understands and adds one hint, rather than refusing
/// to render and leaving the user with no icon after a CDX upgrade.
pub fn read_snapshot(payload: &Value) -> Result<Snapshot, Unavailable> {
    let snapshot = payload.get("snapshot").unwrap_or(payload);
    let schema = snapshot.get("schema").ok_or(Unavailable::NotASnapshot)?;
    if schema.get("name").and_then(Value::as_str) != Some(SCHEMA_NAME) {
        return Err(Unavailable::NotASnapshot);
    }
    let major = schema
        .get("major")
        .and_then(Value::as_u64)
        .ok_or(Unavailable::NotASnapshot)?;
    let icon = snapshot.get("icon").ok_or(Unavailable::NotASnapshot)?;
    Ok(Snapshot {
        events: crate::events::parse_array(snapshot.get("events")),
        // Absent means on: an older CDX has no mute, and defaulting to muted
        // would silence someone who never asked for it.
        spool_path: snapshot
            .get("spool_path")
            .and_then(Value::as_str)
            .filter(|v| !v.is_empty())
            .map(str::to_string),
        alerts_enabled: snapshot
            .get("alerts_enabled")
            .and_then(|v| v.as_bool())
            .unwrap_or(true),
        tooltip: icon
            .get("tooltip")
            .and_then(Value::as_str)
            .unwrap_or("CDX")
            .to_string(),
        icon_state: icon
            .get("state")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
        session_count: icon.get("session_count").and_then(Value::as_u64).unwrap_or(0),
        refreshable: snapshot
            .get("refreshable")
            .and_then(Value::as_bool)
            .unwrap_or(true),
        update_hint: (major > SCHEMA_MAJOR).then(|| {
            format!("This companion reads tray snapshot v{SCHEMA_MAJOR}; CDX emits v{major}. Update the tray companion.")
        }),
        terminal: snapshot
            .get("terminal")
            .and_then(Value::as_str)
            .filter(|name| !name.is_empty())
            .map(str::to_string),
        plugins: snapshot
            .get("plugins")
            .and_then(Value::as_array)
            .map(|cards| cards.iter().filter_map(plugin_card_from).collect())
            .unwrap_or_default(),
        sessions: snapshot
            .get("sessions")
            .and_then(Value::as_array)
            .map(|rows| rows.iter().map(session_from).collect())
            .unwrap_or_default(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cards(payload: &str) -> Vec<PluginCard> {
        let value: Value = serde_json::from_str(payload).expect("valid json");
        read_snapshot(&value).expect("a snapshot").plugins
    }

    fn wrap(plugins: &str) -> String {
        format!(
            r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":1}},
                "icon":{{"state":"ok","tooltip":"CDX","session_count":0}},
                "sessions":[],"plugins":{plugins}}}"#
        )
    }

    /// An older CDX sends no cards at all, and that is the normal case.
    #[test]
    fn a_snapshot_without_plugins_has_none() {
        assert!(cards(&wrap("[]")).is_empty());
        let value: Value = serde_json::from_str(&format!(
            r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":0}},
                "icon":{{"state":"ok","tooltip":"CDX","session_count":0}},"sessions":[]}}"#
        ))
        .expect("valid json");
        assert!(read_snapshot(&value)
            .expect("a snapshot")
            .plugins
            .is_empty());
    }

    /// CDX has been sending both windows since the snapshot existed; only the
    /// companion ignored them. A build that predates this reads neither and
    /// keeps rendering the single figure, which is why nothing about the
    /// payload had to change.
    #[test]
    fn both_limit_windows_are_read_when_cdx_reports_them() {
        let value: Value = serde_json::from_str(&format!(
            r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":1}},
                "icon":{{"state":"low","tooltip":"CDX","session_count":1}},
                "sessions":[{{"name":"work","provider":"claude","available_pct":12,
                    "remaining_5h_pct":80,"remaining_week_pct":12,"freshness":"fresh"}}]}}"#
        ))
        .expect("valid json");
        let session = &read_snapshot(&value).expect("a snapshot").sessions[0];
        assert_eq!(session.five_hour_pct, Some(80.0));
        assert_eq!(session.week_pct, Some(12.0));
        // The figure the icon follows stays the one that runs out first.
        assert_eq!(session.available_pct, Some(12.0));
    }

    /// `req_047` AC2: the preference reaches the companion through the snapshot
    /// it already polls, not through a second store it would have to keep in
    /// step with CDX.
    #[test]
    fn the_chosen_terminal_arrives_with_the_snapshot() {
        let value: Value = serde_json::from_str(&format!(
            r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":2}},
                "icon":{{"state":"ok","tooltip":"CDX","session_count":0}},
                "sessions":[],"terminal":"Ghostty"}}"#
        ))
        .expect("valid json");
        assert_eq!(
            read_snapshot(&value)
                .expect("a snapshot")
                .terminal
                .as_deref(),
            Some("Ghostty")
        );
    }

    /// An older CDX sends no preference, and an empty one is no preference —
    /// either way the platform's own terminal opens.
    #[test]
    fn no_preference_means_the_platform_default() {
        for payload in [
            format!(
                r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":1}},
                    "icon":{{"state":"ok","tooltip":"CDX","session_count":0}},"sessions":[]}}"#
            ),
            format!(
                r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":2}},
                    "icon":{{"state":"ok","tooltip":"CDX","session_count":0}},
                    "sessions":[],"terminal":""}}"#
            ),
        ] {
            let value: Value = serde_json::from_str(&payload).expect("valid json");
            assert_eq!(read_snapshot(&value).expect("a snapshot").terminal, None);
        }
    }

    #[test]
    fn a_session_without_windows_reads_as_having_none() {
        let value: Value = serde_json::from_str(&format!(
            r#"{{"schema":{{"name":"{SCHEMA_NAME}","major":{SCHEMA_MAJOR},"minor":0}},
                "icon":{{"state":"ok","tooltip":"CDX","session_count":1}},
                "sessions":[{{"name":"work","provider":"ollama","available_pct":50,"freshness":"fresh"}}]}}"#
        ))
        .expect("valid json");
        let session = &read_snapshot(&value).expect("a snapshot").sessions[0];
        assert_eq!(session.five_hour_pct, None);
        assert_eq!(session.week_pct, None);
        assert_eq!(session.available_pct, Some(50.0));
    }

    #[test]
    fn a_card_carries_its_rows_and_actions() {
        let parsed = cards(&wrap(
            r#"[{"title":"Logics","summary":"1 blocked","rows":[{"label":"blocked: x","action":"logics.focus:t1"}],"actions":["logics.open"]}]"#,
        ));
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed[0].rows[0].action, "logics.focus:t1");
        assert_eq!(parsed[0].actions, vec!["logics.open".to_string()]);
    }

    /// A section with a title and no meaning is worse than no section.
    #[test]
    fn a_card_without_a_title_or_summary_is_dropped() {
        assert!(cards(&wrap(r#"[{"summary":"1 blocked"}]"#)).is_empty());
        assert!(cards(&wrap(r#"[{"title":"Logics"}]"#)).is_empty());
        assert!(cards(&wrap(r#"["nonsense", 7, null]"#)).is_empty());
    }

    /// The companion re-reads CDX's own bound rather than trusting it: a menu
    /// that grew with an integration would stop being a quota menu.
    #[test]
    fn a_card_cannot_contribute_more_than_two_rows() {
        let rows = (0..6)
            .map(|i| format!(r#"{{"label":"row {i}","action":"logics.focus:t{i}"}}"#))
            .collect::<Vec<_>>()
            .join(",");
        let parsed = cards(&wrap(&format!(
            r#"[{{"title":"Logics","summary":"s","rows":[{rows}]}}]"#
        )));
        assert_eq!(parsed[0].rows.len(), MAX_PLUGIN_ROWS);
    }

    #[test]
    fn a_row_without_a_usable_action_is_dropped() {
        let parsed = cards(&wrap(
            r#"[{"title":"Logics","summary":"s","rows":[{"label":"no action"},{"label":"","action":"logics.open"}]}]"#,
        ));
        assert!(parsed[0].rows.is_empty());
    }

    fn snapshot_json(major: u64) -> Value {
        serde_json::json!({
            "schema": {"name": SCHEMA_NAME, "major": major, "minor": 0},
            "icon": {"state": "low", "reason": "fresh", "session_count": 2,
                     "tooltip": "CDX · capacity low · 18% left"},
            "refreshable": false,
            "sessions": [
                {"name": "work", "provider": "codex", "available_pct": 18,
                 "freshness": "fresh", "reset_at": "2026-08-11T09:00"},
                {"name": "side", "provider": "claude", "available_pct": null,
                 "freshness": "unknown", "reset_at": null}
            ]
        })
    }

    #[test]
    fn reads_a_current_snapshot() {
        let parsed = read_snapshot(&snapshot_json(SCHEMA_MAJOR)).expect("readable");
        assert_eq!(parsed.icon_state, "low");
        assert_eq!(parsed.tooltip, "CDX · capacity low · 18% left");
        assert_eq!(parsed.session_count, 2);
        assert!(!parsed.refreshable);
        assert!(parsed.update_hint.is_none());
        assert_eq!(parsed.sessions.len(), 2);
        assert_eq!(parsed.sessions[0].available_pct, Some(18.0));
        assert_eq!(parsed.sessions[1].available_pct, None);
        assert_eq!(parsed.sessions[1].freshness, "unknown");
    }

    #[test]
    fn a_newer_major_still_renders_with_a_hint() {
        let parsed = read_snapshot(&snapshot_json(SCHEMA_MAJOR + 1)).expect("readable");
        assert_eq!(parsed.icon_state, "low");
        assert!(parsed.update_hint.is_some());
        assert_eq!(
            parsed.sessions.len(),
            2,
            "known fields survive an unknown major"
        );
    }

    #[test]
    fn unwraps_the_cli_envelope() {
        // `cdx tray status --json` wraps the snapshot in its JSON success
        // envelope; the companion must read either shape.
        let enveloped = serde_json::json!({"ok": true, "snapshot": snapshot_json(SCHEMA_MAJOR)});
        assert_eq!(
            read_snapshot(&enveloped).expect("readable").icon_state,
            "low"
        );
    }

    #[test]
    fn a_snapshot_without_sessions_is_not_an_error() {
        let mut payload = snapshot_json(SCHEMA_MAJOR);
        payload.as_object_mut().unwrap().remove("sessions");
        assert!(read_snapshot(&payload)
            .expect("readable")
            .sessions
            .is_empty());
    }

    #[test]
    fn an_old_cdx_is_named_rather_than_dumped() {
        // Drift the other way: the companion is newer than CDX. Reading the
        // published error code beats matching the message text.
        let stderr =
            r#"{"ok":false,"error":{"code":"unknown_command","message":"Unknown command: tray."}}"#;
        assert_eq!(error_code(stderr).as_deref(), Some("unknown_command"));
        assert!(error_code("not json at all").is_none());
        assert!(error_code(r#"{"ok":false}"#).is_none());
    }

    #[test]
    fn foreign_json_is_refused_rather_than_guessed() {
        for payload in [
            serde_json::json!({}),
            serde_json::json!({"schema": {"name": "something.else", "major": 1}}),
            serde_json::json!({"schema": {"name": SCHEMA_NAME}}),
        ] {
            assert!(read_snapshot(&payload).is_err(), "{payload}");
        }
    }

    #[test]
    fn settings_survive_a_cmd_exe_trailing_space() {
        // `set VAR=1 && ...` in cmd.exe stores "1 ". Untrimmed, that silently
        // selected the native transport on the one platform that needs WSL.
        std::env::set_var("CDX_TRAY_TEST_SETTING", "Ubuntu ");
        assert_eq!(setting("CDX_TRAY_TEST_SETTING").as_deref(), Some("Ubuntu"));
        std::env::set_var("CDX_TRAY_TEST_SETTING", "   ");
        assert_eq!(setting("CDX_TRAY_TEST_SETTING"), None);
        std::env::remove_var("CDX_TRAY_TEST_SETTING");
        assert_eq!(setting("CDX_TRAY_TEST_SETTING"), None);
    }

    #[test]
    fn wsl_transport_builds_an_interop_command() {
        let described = Transport::Wsl {
            distro: Some("Ubuntu".into()),
        }
        .describe();
        assert_eq!(described, "wsl.exe -d Ubuntu -- cdx tray status --json");
        assert_eq!(
            Transport::Wsl { distro: None }.describe(),
            "wsl.exe -- cdx tray status --json"
        );
        assert!(Transport::Wsl { distro: None }.is_wsl());
        assert!(!Transport::Native.is_wsl());
    }
}
