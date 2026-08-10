//! Which WSL distribution the companion talks to.
//!
//! `adr_005` fixes the policy: the default distribution unless an explicit name
//! is configured, and never an aggregate of several. This module makes that
//! deterministic and, more importantly, makes a wrong name say so.
//!
//! A misconfigured distribution name would otherwise surface as "CDX not found
//! on this host", which is true of the distribution that does not exist and
//! useless as a diagnosis.

/// `wsl.exe -l` writes UTF-16LE, not UTF-8. Decoded as UTF-8 the names come out
/// interleaved with NUL bytes, which is why a naive `contains("Ubuntu")` check
/// fails against real output.
pub fn decode_utf16le(bytes: &[u8]) -> String {
    let units: Vec<u16> = bytes
        .chunks_exact(2)
        .map(|pair| u16::from_le_bytes([pair[0], pair[1]]))
        .collect();
    String::from_utf16_lossy(&units)
}

/// Installed distributions, in the order `wsl.exe` lists them.
pub fn parse_list(output: &str) -> Vec<String> {
    output
        .lines()
        .map(|line| line.trim().trim_end_matches('\r').to_string())
        .filter(|line| !line.is_empty())
        .collect()
}

#[derive(Debug, PartialEq, Eq)]
pub enum Resolution {
    /// Use this distribution explicitly.
    Named(String),
    /// No name configured: `wsl.exe` picks its own default, which is exactly the
    /// policy adr_005 wanted and needs no parsing on our side.
    Default,
    /// A name was configured and no such distribution exists. Carries the
    /// installed ones so the message can list what the user could have meant.
    Unknown {
        wanted: String,
        installed: Vec<String>,
    },
    /// WSL itself could not be queried.
    Unavailable(String),
}

/// Resolve the configured name against what is actually installed.
///
/// Deterministic by construction: a name either matches an installed
/// distribution or is reported as unknown. There is no fallback to the default,
/// because silently using a different distribution than the one configured is
/// exactly the kind of helpfulness that makes a wrong reading impossible to
/// diagnose.
pub fn resolve(configured: Option<&str>, list: Result<Vec<String>, String>) -> Resolution {
    let Some(wanted) = configured else {
        return Resolution::Default;
    };
    match list {
        Err(reason) => Resolution::Unavailable(reason),
        Ok(installed) => {
            if installed
                .iter()
                .any(|name| name.eq_ignore_ascii_case(wanted))
            {
                Resolution::Named(wanted.to_string())
            } else {
                Resolution::Unknown {
                    wanted: wanted.to_string(),
                    installed,
                }
            }
        }
    }
}

impl Resolution {
    /// What to tell the user. `None` when there is nothing wrong to say.
    pub fn problem(&self) -> Option<String> {
        match self {
            Resolution::Named(_) | Resolution::Default => None,
            Resolution::Unknown { wanted, installed } => Some(if installed.is_empty() {
                format!("WSL distribution `{wanted}` is not installed, and no distribution is.")
            } else {
                format!(
                    "WSL distribution `{wanted}` is not installed. Installed: {}.",
                    installed.join(", ")
                )
            }),
            Resolution::Unavailable(reason) => Some(format!("Could not query WSL: {reason}")),
        }
    }
}

/// Ask `wsl.exe` what is installed. Not gated to Windows: elsewhere the command
/// is simply absent, and "could not query WSL" is the honest answer to a user
/// who asked for the WSL transport on a machine that has no WSL.
pub fn installed() -> Result<Vec<String>, String> {
    let output = std::process::Command::new("wsl.exe")
        .args(["-l", "-q"])
        .output()
        .map_err(|error| format!("wsl.exe could not be run ({error})"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    Ok(parse_list(&decode_utf16le(&output.stdout)))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Real `wsl.exe -l -q` output: UTF-16LE, one name per line.
    fn utf16le(text: &str) -> Vec<u8> {
        text.encode_utf16()
            .flat_map(|unit| unit.to_le_bytes())
            .collect()
    }

    #[test]
    fn utf16le_output_decodes_to_real_names() {
        // Decoded as UTF-8 this reads "U b u n t u", which is why the naive
        // check passes for the wrong reason and fails for the right one.
        let decoded = decode_utf16le(&utf16le("Ubuntu\r\ndocker-desktop\r\n"));
        assert_eq!(parse_list(&decoded), vec!["Ubuntu", "docker-desktop"]);
    }

    #[test]
    fn no_configured_name_means_the_wsl_default() {
        assert_eq!(
            resolve(None, Ok(vec!["Ubuntu".into()])),
            Resolution::Default
        );
    }

    #[test]
    fn a_configured_name_is_matched_case_insensitively() {
        let installed = Ok(vec!["Ubuntu".to_string()]);
        assert_eq!(
            resolve(Some("ubuntu"), installed),
            Resolution::Named("ubuntu".into())
        );
    }

    #[test]
    fn an_unknown_name_lists_what_is_installed_rather_than_falling_back() {
        // Falling back to the default would read quota from a different
        // distribution than the one configured, which is undiagnosable.
        let resolution = resolve(
            Some("Debian"),
            Ok(vec!["Ubuntu".into(), "docker-desktop".into()]),
        );
        let problem = resolution.problem().expect("a problem");
        assert!(problem.contains("Debian"), "{problem}");
        assert!(problem.contains("Ubuntu, docker-desktop"), "{problem}");
    }

    #[test]
    fn no_distribution_at_all_says_so() {
        let problem = resolve(Some("Ubuntu"), Ok(vec![]))
            .problem()
            .expect("a problem");
        assert!(problem.contains("no distribution is"), "{problem}");
    }

    #[test]
    fn an_unqueryable_wsl_is_reported_as_such() {
        let problem = resolve(Some("Ubuntu"), Err("not installed".into()))
            .problem()
            .expect("a problem");
        assert!(problem.contains("Could not query WSL"), "{problem}");
    }
}
