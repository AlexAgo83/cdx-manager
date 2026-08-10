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
    pub available_pct: Option<f64>,
    pub freshness: String,
    pub reset_at: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Snapshot {
    pub icon_state: String,
    /// What the closed icon may say on hover. Built by CDX so the companion
    /// cannot accidentally compose something the privacy rule forbids.
    pub tooltip: String,
    pub session_count: u64,
    pub refreshable: bool,
    /// Set when the snapshot is newer than this build understands.
    pub update_hint: Option<String>,
    pub sessions: Vec<Session>,
}

pub fn fetch(transport: &Transport) -> Result<Snapshot, Unavailable> {
    // Check the distribution before blaming CDX for being absent from it.
    if let Transport::Wsl { distro: Some(name) } = transport {
        let resolution = crate::wsl::resolve(Some(name), crate::wsl::installed());
        if let Some(problem) = resolution.problem() {
            return Err(Unavailable::WslDistro(problem));
        }
    }
    let output = transport
        .command()
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
        available_pct: value.get("available_pct").and_then(Value::as_f64),
        freshness: value
            .get("freshness")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
        reset_at: value
            .get("reset_at")
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
