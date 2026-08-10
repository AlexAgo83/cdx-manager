//! The CDX tray companion.
//!
//! This is the build-capability slice, not the tray. It proves the one thing
//! the native side actually risks getting wrong: that a separate process can
//! obtain the snapshot, natively and across the WSL boundary, and refuse
//! honestly when it cannot. `item_080` adds the icon and the menu on top.
//!
//! Per `adr_005` the transport is `cdx` itself, invoked as a child process,
//! and the snapshot arrives on stdout. There is no status file, no socket, and
//! no provider call from here.

use std::process::Command;

use serde_json::Value;

const SCHEMA_NAME: &str = "cdx.tray.snapshot";
/// The snapshot major this build understands. A newer major is readable, not
/// fatal: CDX and the companion update separately and drift is the normal
/// state, so we render what we know and say an update is available.
const SCHEMA_MAJOR: u64 = 1;

/// How to reach `cdx`. On a Windows host serving CDX inside WSL the command is
/// the same, wrapped in an interop call, because WSL localhost is directional
/// and a socket would be a worse bet than a process.
enum Transport {
    Native,
    Wsl { distro: Option<String> },
}

impl Transport {
    /// `CDX_TRAY_WSL=1` selects interop, `CDX_TRAY_WSL_DISTRO` names a
    /// distribution. Environment rather than config file for now: item_085
    /// owns the real resolution, including the default-distribution rules.
    fn from_env() -> Self {
        match std::env::var("CDX_TRAY_WSL").ok().as_deref() {
            Some("1") | Some("true") => Transport::Wsl {
                distro: std::env::var("CDX_TRAY_WSL_DISTRO")
                    .ok()
                    .filter(|d| !d.is_empty()),
            },
            _ => Transport::Native,
        }
    }

    fn command(&self) -> Command {
        match self {
            Transport::Native => {
                let mut cmd = Command::new("cdx");
                cmd.args(["tray", "status", "--json"]);
                cmd
            }
            Transport::Wsl { distro } => {
                let mut cmd = Command::new("wsl.exe");
                if let Some(name) = distro {
                    cmd.args(["-d", name]);
                }
                cmd.args(["--", "cdx", "tray", "status", "--json"]);
                cmd
            }
        }
    }

    fn describe(&self) -> String {
        match self {
            Transport::Native => "cdx tray status --json".to_string(),
            Transport::Wsl { distro: Some(d) } => {
                format!("wsl.exe -d {d} -- cdx tray status --json")
            }
            Transport::Wsl { distro: None } => "wsl.exe -- cdx tray status --json".to_string(),
        }
    }
}

/// Why the companion has nothing to show. Every variant is a state the tray
/// must be able to render honestly; none of them may become a fabricated quota.
#[derive(Debug)]
enum Unavailable {
    CdxNotFound(String),
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

struct Snapshot {
    icon_state: String,
    session_count: u64,
    refreshable: bool,
    /// Set when the snapshot is newer than this build understands.
    update_hint: Option<String>,
}

fn fetch(transport: &Transport) -> Result<Snapshot, Unavailable> {
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

/// Mirrors `read_snapshot` in `src/tray_contract.py`: an unknown major keeps
/// every field this reader understands and adds one hint, rather than refusing
/// to render and leaving the user with no icon after a CDX upgrade.
fn read_snapshot(payload: &Value) -> Result<Snapshot, Unavailable> {
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
        icon_state: icon
            .get("state")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
        session_count: icon.get("session_count").and_then(Value::as_u64).unwrap_or(0),
        refreshable: snapshot.get("refreshable").and_then(Value::as_bool).unwrap_or(true),
        update_hint: (major > SCHEMA_MAJOR).then(|| {
            format!("This companion reads tray snapshot v{SCHEMA_MAJOR}; CDX emits v{major}. Update the tray companion.")
        }),
    })
}

fn main() {
    let transport = Transport::from_env();
    match fetch(&transport) {
        Ok(snapshot) => {
            println!("icon: {}", snapshot.icon_state);
            println!("sessions: {}", snapshot.session_count);
            if !snapshot.refreshable {
                println!("refresh: unavailable while a session holds the provider lock");
            }
            if let Some(hint) = snapshot.update_hint {
                println!("hint: {hint}");
            }
        }
        Err(reason) => {
            // Unavailable is a state, not a crash: the tray must be able to
            // show "I do not know" without inventing a quota figure.
            println!("icon: unavailable");
            eprintln!("cdx-tray: {reason}");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot_json(major: u64) -> Value {
        serde_json::json!({
            "schema": {"name": SCHEMA_NAME, "major": major, "minor": 0},
            "icon": {"state": "low", "reason": "fresh", "session_count": 2},
            "refreshable": false,
            "sessions": []
        })
    }

    #[test]
    fn reads_a_current_snapshot() {
        let parsed = read_snapshot(&snapshot_json(SCHEMA_MAJOR)).expect("readable");
        assert_eq!(parsed.icon_state, "low");
        assert_eq!(parsed.session_count, 2);
        assert!(!parsed.refreshable);
        assert!(parsed.update_hint.is_none());
    }

    #[test]
    fn a_newer_major_still_renders_with_a_hint() {
        let parsed = read_snapshot(&snapshot_json(SCHEMA_MAJOR + 1)).expect("readable");
        assert_eq!(parsed.icon_state, "low");
        assert!(parsed.update_hint.is_some());
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
    }
}
