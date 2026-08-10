//! The CDX tray companion.
//!
//! Two modes. By default it puts an icon in the menu bar and stays there. With
//! `--print` it renders the same menu to stdout once and exits, which is how
//! the contract, the poll cadence, and the unavailable states get exercised on
//! a machine with no windowing session.

mod backend;
#[cfg(target_os = "macos")]
mod mac;
mod menu;
mod runner;
mod schedule;
mod snapshot;
#[cfg(target_os = "windows")]
mod win;

use menu::Entry;
use schedule::Tick;
use snapshot::{fetch, Transport};

fn render(entries: &[Entry]) {
    for entry in entries {
        match entry {
            Entry::Info(text) => println!("  {text}"),
            Entry::Separator => println!("  ---"),
            Entry::Action { label, enabled, .. } => {
                println!("  [{}] {label}", if *enabled { "x" } else { " " })
            }
        }
    }
}

/// One snapshot, rendered to stdout. Exits non-zero when CDX could not be
/// reached, so a script can tell "nothing known" from "all fine".
fn print_once(transport: &Transport) -> i32 {
    match fetch(transport) {
        Ok(snap) => {
            let tick = Tick::start().succeeded(snap.session_count);
            render(&menu::build(&snap));
            match tick.next_delay(transport.is_wsl()) {
                Some(delay) => println!("next poll in {}s", delay.as_secs()),
                None => println!("no enabled session: polling stopped"),
            }
            0
        }
        Err(reason) => {
            render(&menu::build_unavailable(&reason));
            eprintln!("cdx-tray: {reason}");
            1
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let transport = Transport::from_env();

    match args.first().map(String::as_str) {
        Some("--print") => std::process::exit(print_once(&transport)),
        Some("--help" | "-h") => {
            println!("cdx-tray            run the CDX menu bar companion");
            println!("cdx-tray --print    render the menu once and exit");
            println!();
            println!("CDX_TRAY_WSL=1              reach CDX through WSL interop");
            println!("CDX_TRAY_WSL_DISTRO=NAME    use a named WSL distribution");
            println!("CDX_TRAY_CDX=PATH          run this cdx instead of `cdx` on PATH");
        }
        Some(other) => {
            eprintln!("cdx-tray: unknown argument {other}. Try --help.");
            std::process::exit(2);
        }
        None => run_tray(transport),
    }
}

#[cfg(target_os = "macos")]
fn run_tray(transport: Transport) {
    if let Err(reason) = mac::run(transport) {
        eprintln!("cdx-tray: {reason}");
        std::process::exit(1);
    }
}

#[cfg(target_os = "windows")]
fn run_tray(transport: Transport) {
    if let Err(reason) = win::run(transport) {
        eprintln!("cdx-tray: {reason}");
        std::process::exit(1);
    }
}

/// The Linux backend lands with item_081, on ksni rather than tray-icon. Until then the
/// companion says so rather than starting something that cannot draw.
#[cfg(not(any(target_os = "macos", target_os = "windows")))]
fn run_tray(transport: Transport) {
    eprintln!(
        "cdx-tray: no tray backend on this platform yet. `cdx-tray --print` works everywhere."
    );
    std::process::exit(print_once(&transport));
}
