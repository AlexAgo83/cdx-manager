//! The CDX tray companion.
//!
//! The tray backend is not wired yet; `item_080` adds `tray-icon` and `muda` on
//! top of what is here. This binary already carries the parts that can be
//! verified without a windowing session: obtaining the snapshot, deciding when
//! it may ask again, and building the menu the backend will render.
//!
//! Running it prints that menu to stdout, which is also how the poll cadence
//! and the unavailable states get exercised on a real machine.

mod menu;
mod schedule;
mod snapshot;

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

fn main() {
    let transport = Transport::from_env();
    match fetch(&transport) {
        Ok(snap) => {
            let tick = Tick::start().succeeded(snap.session_count);
            render(&menu::build(&snap));
            match tick.next_delay(transport.is_wsl()) {
                Some(delay) => println!("next poll in {}s", delay.as_secs()),
                None => println!("no enabled session: polling stopped"),
            }
        }
        Err(reason) => {
            // Unavailable is a state, not a crash: the tray must be able to
            // show "I do not know" without inventing a quota figure.
            render(&menu::build_unavailable(&reason));
            let tick = Tick::start().failed();
            if let Some(delay) = tick.next_delay(transport.is_wsl()) {
                println!("next poll in {}s", delay.as_secs());
            }
            std::process::exit(1);
        }
    }
}
