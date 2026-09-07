//! How a Windows tray turns a cdx action into a process to spawn.
//!
//! Not gated to Windows, and that is the point: the interesting part is the
//! shape of the command, which is exactly what a Windows-only module could not
//! be tested for on any other host. `win.rs` does the spawning; the decisions
//! are here, where `cargo test` reaches them everywhere.
//!
//! Two rules the review found broken, both of them about the Windows-to-WSL
//! crossing:
//!
//! * A cdx action can need several arguments. `wsl.exe -- cdx "config work1"`
//!   hands CDX one session name that happens to contain a space, so the parts
//!   travel as separate argv elements wherever the crossing is a real process
//!   rather than a shell string.
//! * `cmd.exe` is not PowerShell. It has no `-NoExit -Command`; the verified
//!   form is `cmd /k <command>`.

use crate::snapshot::Transport;

/// The terminal preferences a Windows companion knows how to launch.
///
/// Windows has no convention for asking an arbitrary terminal to run a command,
/// so this list is closed by necessity rather than by choice: each entry is one
/// this module can build a working command line for.
pub const SUPPORTED: [(&str, &str); 4] = [
    ("wt", "wt.exe"),
    ("powershell", "powershell.exe"),
    ("pwsh", "pwsh.exe"),
    ("cmd", "cmd.exe"),
];

/// A process to start: the program, and its argv.
#[derive(Debug, PartialEq, Eq)]
pub struct Spawn {
    pub program: String,
    pub args: Vec<String>,
}

fn owned(parts: &[&str]) -> Vec<String> {
    parts.iter().map(|part| (*part).to_string()).collect()
}

/// Is this executable on PATH?
///
/// Written out rather than shelled out to `where`: the answer gates a menu that
/// is rebuilt every poll, and spawning four processes for it would cost more
/// than the poll itself.
pub fn on_path(program: &str) -> bool {
    std::env::var_os("PATH")
        .map(|paths| std::env::split_paths(&paths).any(|dir| dir.join(program).is_file()))
        .unwrap_or(false)
}

/// The terminal choices this companion can actually offer.
///
/// CDX serialises its candidate list from the host that answered the poll, and
/// under WSL transport that host is Linux: it offers `x-terminal-emulator` and
/// friends, none of which a Windows process can open. What the menu may show is
/// decided here, on the side that does the launching.
pub fn options(exists: impl Fn(&str) -> bool) -> Vec<String> {
    SUPPORTED
        .iter()
        .filter(|(_, program)| exists(program))
        .map(|(name, _)| (*name).to_string())
        .collect()
}

/// The stored preference to honour, or `None` for the default console.
///
/// A preference this companion cannot launch is not an error to report and sit
/// on: the click still has to open something. It falls back to the console that
/// has always opened.
pub fn honoured(preference: Option<&str>, options: &[String]) -> Option<String> {
    let name = preference?;
    options
        .iter()
        .find(|option| option.eq_ignore_ascii_case(name))
        .cloned()
}

/// Trim a snapshot's terminal choices to what this companion can launch, and
/// drop a stored preference that is not among them.
pub fn restrict(
    candidates: &mut Vec<String>,
    preference: &mut Option<String>,
    options: Vec<String>,
) {
    *preference = honoured(preference.as_deref(), &options);
    *candidates = options;
}

/// The cdx command as it crosses to WSL: separate argv elements.
fn wsl_argv<'a>(distro: Option<&'a str>, cdx: &'a str, args: &[&'a str]) -> Vec<String> {
    let mut argv = vec!["wsl.exe".to_string()];
    if let Some(name) = distro {
        argv.extend(owned(&["-d", name]));
    }
    argv.push("--".to_string());
    argv.push(cdx.to_string());
    argv.extend(owned(args));
    argv
}

/// The cdx command as a shell string, for the terminals that take one.
///
/// Joining is safe because every part is either a fixed subcommand or a session
/// name CDX has already validated as a bare identifier; nothing here can carry
/// a shell fragment. The alternative — a terminal preference that could hold a
/// command line — is the thing `tray_terminal` exists to make impossible.
fn shell_command(transport: &Transport, cdx: &str, args: &[&str]) -> String {
    let tail = if args.is_empty() {
        String::new()
    } else {
        format!(" {}", args.join(" "))
    };
    match transport {
        Transport::Native => format!("{cdx}{tail}"),
        Transport::Wsl { distro: Some(name) } => format!("wsl.exe -d {name} -- {cdx}{tail}"),
        Transport::Wsl { distro: None } => format!("wsl.exe -- {cdx}{tail}"),
    }
}

/// The console that has always opened: a detached `cmd /c start`.
pub fn default_console(transport: &Transport, cdx: &str, args: &[&str]) -> Spawn {
    let mut argv = owned(&["/c", "start", ""]);
    match transport {
        Transport::Wsl { distro } => argv.extend(wsl_argv(distro.as_deref(), cdx, args)),
        Transport::Native => {
            argv.extend(owned(&["cmd", "/k"]));
            argv.push(shell_command(transport, cdx, args));
        }
    }
    Spawn {
        program: "cmd".to_string(),
        args: argv,
    }
}

/// The command for a preferred terminal, or `None` when it is not one this
/// companion can launch.
pub fn preferred_console(
    transport: &Transport,
    preference: &str,
    cdx: &str,
    args: &[&str],
) -> Option<Spawn> {
    let name = preference.to_ascii_lowercase();
    let (name, program) = SUPPORTED
        .iter()
        .find(|(supported, _)| *supported == name)?;
    let args = match (*name, transport) {
        // `wt -- <command>` is documented, so the command crosses as a real
        // argv and the cdx parts stay separate.
        ("wt", Transport::Wsl { distro }) => {
            let mut argv = owned(&["-w", "0", "nt", "--"]);
            argv.extend(wsl_argv(distro.as_deref(), cdx, args));
            argv
        }
        ("wt", Transport::Native) => {
            let mut argv = owned(&["-w", "0", "nt", "--", "cmd", "/k"]);
            argv.push(shell_command(transport, cdx, args));
            argv
        }
        // cmd takes `/k <command>`, never PowerShell's `-NoExit -Command`,
        // which it accepts and then does not run.
        ("cmd", _) => {
            let mut argv = owned(&["/k"]);
            argv.push(shell_command(transport, cdx, args));
            argv
        }
        (_, _) => {
            let mut argv = owned(&["-NoExit", "-Command"]);
            argv.push(shell_command(transport, cdx, args));
            argv
        }
    };
    Some(Spawn {
        program: (*program).to_string(),
        args,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn wsl() -> Transport {
        Transport::Wsl {
            distro: Some("Ubuntu".to_string()),
        }
    }

    #[test]
    fn a_multi_argument_action_crosses_to_wsl_as_separate_arguments() {
        // `wsl.exe -- cdx "config work1"` reports `Unknown session: config
        // work1`, which is the whole defect.
        let spawn = default_console(&wsl(), "cdx", &["config", "work1"]);
        assert_eq!(spawn.program, "cmd");
        assert_eq!(
            spawn.args,
            vec![
                "/c", "start", "", "wsl.exe", "-d", "Ubuntu", "--", "cdx", "config", "work1"
            ]
        );
    }

    #[test]
    fn windows_terminal_keeps_the_cdx_arguments_separate_across_wsl() {
        let spawn = preferred_console(&wsl(), "wt", "cdx", &["config", "work1"]).expect("wt");
        assert_eq!(spawn.program, "wt.exe");
        assert_eq!(
            spawn.args,
            vec![
                "-w", "0", "nt", "--", "wsl.exe", "-d", "Ubuntu", "--", "cdx", "config", "work1"
            ]
        );
    }

    #[test]
    fn a_cmd_preference_runs_the_command_instead_of_opening_an_idle_shell() {
        // `cmd.exe -NoExit -Command echo hi` opens a prompt and runs nothing.
        let spawn = preferred_console(&wsl(), "cmd", "cdx", &["config", "work1"]).expect("cmd");
        assert_eq!(spawn.program, "cmd.exe");
        assert_eq!(
            spawn.args,
            vec!["/k", "wsl.exe -d Ubuntu -- cdx config work1"]
        );
        assert!(!spawn.args.iter().any(|arg| arg == "-NoExit"));

        let native = preferred_console(&Transport::Native, "CMD", "cdx", &["status"]).expect("cmd");
        assert_eq!(native.args, vec!["/k", "cdx status"]);
    }

    #[test]
    fn powershell_still_takes_a_command_string() {
        let spawn =
            preferred_console(&wsl(), "powershell", "cdx", &["config", "work1"]).expect("ps");
        assert_eq!(spawn.program, "powershell.exe");
        assert_eq!(
            spawn.args,
            vec!["-NoExit", "-Command", "wsl.exe -d Ubuntu -- cdx config work1"]
        );
        let default_distro = preferred_console(
            &Transport::Wsl { distro: None },
            "pwsh",
            "/home/a/.local/bin/cdx",
            &["status"],
        )
        .expect("pwsh");
        assert_eq!(default_distro.program, "pwsh.exe");
        assert_eq!(
            default_distro.args,
            vec!["-NoExit", "-Command", "wsl.exe -- /home/a/.local/bin/cdx status"]
        );
    }

    #[test]
    fn a_terminal_this_companion_cannot_launch_has_no_command() {
        assert!(preferred_console(&wsl(), "x-terminal-emulator", "cdx", &["status"]).is_none());
        assert!(preferred_console(&wsl(), "Ghostty", "cdx", &["status"]).is_none());
    }

    #[test]
    fn only_terminals_present_on_this_host_are_offered() {
        // The real Tower host: wt and cmd and powershell, no pwsh.
        let present = ["wt.exe", "powershell.exe", "cmd.exe"];
        assert_eq!(
            options(|program| present.contains(&program)),
            vec!["wt", "powershell", "cmd"]
        );
        assert!(options(|_| false).is_empty());
    }

    #[test]
    fn a_wsl_produced_candidate_list_is_replaced_by_what_windows_can_open() {
        // What `cdx tray status --json` actually returned from Ubuntu WSL.
        let mut candidates = vec!["x-terminal-emulator".to_string()];
        let mut preference = Some("x-terminal-emulator".to_string());
        restrict(
            &mut candidates,
            &mut preference,
            options(|program| program == "cmd.exe" || program == "wt.exe"),
        );
        assert_eq!(candidates, vec!["wt", "cmd"]);
        // Unsupported stored preference: the default console, not an inert
        // click and a log line.
        assert_eq!(preference, None);
    }

    #[test]
    fn a_supported_stored_preference_survives_the_restriction() {
        let mut candidates = vec!["x-terminal-emulator".to_string()];
        let mut preference = Some("CMD".to_string());
        restrict(
            &mut candidates,
            &mut preference,
            options(|program| program == "cmd.exe"),
        );
        assert_eq!(candidates, vec!["cmd"]);
        assert_eq!(preference.as_deref(), Some("cmd"));
    }
}
