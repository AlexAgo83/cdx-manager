//! The native tray backend: entries in, menu bar out.
//!
//! Everything decided elsewhere. This module owns no policy — it turns
//! `menu::Entry` values into `muda` items, picks the glyph for a state, and
//! runs the platform event loop. Keeping it that thin is what lets the menu
//! model and the poll cadence be tested without a windowing session.

use std::collections::HashMap;

use muda::{CheckMenuItem, Menu, MenuId, MenuItem, PredefinedMenuItem, Submenu};
use tray_icon::{Icon, TrayIcon, TrayIconBuilder};

use crate::menu::{ActionId, Entry};

/// The glyphs, compiled in. They are a few hundred bytes each and the companion
/// must render an icon before it can report that anything is wrong, so a
/// missing file on disk is not a failure mode worth having.
const DARK_OK: &[u8] = include_bytes!("../assets/icons/CDXTemplate-ok.png");
const DARK_LOW: &[u8] = include_bytes!("../assets/icons/CDXTemplate-low.png");
const DARK_CRITICAL: &[u8] = include_bytes!("../assets/icons/CDXTemplate-critical.png");
const DARK_UNKNOWN: &[u8] = include_bytes!("../assets/icons/CDXTemplate-unknown.png");
const LIGHT_OK: &[u8] = include_bytes!("../assets/icons/CDXLight-ok.png");
const LIGHT_LOW: &[u8] = include_bytes!("../assets/icons/CDXLight-low.png");
const LIGHT_CRITICAL: &[u8] = include_bytes!("../assets/icons/CDXLight-critical.png");
const LIGHT_UNKNOWN: &[u8] = include_bytes!("../assets/icons/CDXLight-unknown.png");

/// `light` asks for the white glyph, the one that reads on a dark background.
pub fn glyph_bytes(state: &str, light: bool) -> &'static [u8] {
    match (state, light) {
        ("ok", false) => DARK_OK,
        ("low", false) => DARK_LOW,
        ("critical", false) => DARK_CRITICAL,
        ("ok", true) => LIGHT_OK,
        ("low", true) => LIGHT_LOW,
        ("critical", true) => LIGHT_CRITICAL,
        // Anything unrecognised, including a state a newer CDX invented, shows
        // the unknown glyph rather than no icon at all.
        (_, true) => LIGHT_UNKNOWN,
        (_, false) => DARK_UNKNOWN,
    }
}

/// Whether the tray needs the white glyph.
///
/// macOS never does: it takes the black one as a template image and inverts it
/// per theme itself. Windows has no such concept — `with_icon_as_template` is a
/// macOS-only flag — so a black glyph on a dark taskbar is simply invisible,
/// which is what a real Windows host showed before this existed. There the
/// colour has to be chosen from the taskbar theme.
#[cfg(target_os = "windows")]
pub fn wants_light_glyph() -> bool {
    // 0 means a dark taskbar. Absent or unreadable, assume dark: Windows 11
    // ships dark by default, and a white glyph on a light taskbar is faint
    // while a black one on a dark taskbar is gone entirely.
    match std::process::Command::new("reg")
        .args([
            "query",
            r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            "/v",
            "SystemUsesLightTheme",
        ])
        .output()
    {
        Ok(out) => !String::from_utf8_lossy(&out.stdout).contains("0x1"),
        Err(_) => true,
    }
}

#[cfg(not(target_os = "windows"))]
pub fn wants_light_glyph() -> bool {
    false
}

fn icon_for(state: &str) -> Result<Icon, String> {
    let bytes = glyph_bytes(state, wants_light_glyph());
    let decoded = image_from_png(bytes)?;
    Icon::from_rgba(decoded.0, decoded.1, decoded.2).map_err(|e| e.to_string())
}

/// Decode the small template PNGs without pulling in an image crate: they are
/// 18 and 36 pixel greyscale-plus-alpha files we produced ourselves.
fn image_from_png(bytes: &[u8]) -> Result<(Vec<u8>, u32, u32), String> {
    let decoder = png::Decoder::new(std::io::Cursor::new(bytes));
    let mut reader = decoder.read_info().map_err(|e| e.to_string())?;
    let size = reader
        .output_buffer_size()
        .ok_or("glyph png declares no decodable size")?;
    let mut buf = vec![0; size];
    let info = reader.next_frame(&mut buf).map_err(|e| e.to_string())?;
    let rgba = match info.color_type {
        png::ColorType::Rgba => buf[..info.buffer_size()].to_vec(),
        png::ColorType::Grayscale | png::ColorType::GrayscaleAlpha | png::ColorType::Rgb => {
            return Err(format!(
                "unexpected glyph colour type {:?}",
                info.color_type
            ))
        }
        png::ColorType::Indexed => return Err("indexed glyph png".into()),
    };
    Ok((rgba, info.width, info.height))
}

/// Build the native menu, and the map from generated item id back to the action
/// it stands for. muda hands back an id on click, so the mapping has to be kept.
/// Give the session rows a drawn cell where the platform allows one.
///
/// Called while the menu is still owned here, because the pointer it exposes is
/// only reachable through the `ContextMenu` trait. macOS is the only platform
/// with somewhere to draw: Win32 would need owner-draw and a
/// StatusNotifierItem menu is a D-Bus description, so the other two keep the
/// text rows — which is why the text still says everything the drawing does.
#[cfg(target_os = "macos")]
fn style_rows(menu: &Menu, rows: &[crate::runner::Row]) {
    use muda::ContextMenu;
    // Same pointer, same moment: the menu is rebuilt on every redraw, so the
    // delegate that reports it being opened has to be re-set with it.
    crate::mac_menu_open::observe(menu.ns_menu());
    let cells: Vec<crate::mac_cell::Cell> = rows
        .iter()
        .map(|row| crate::mac_cell::Cell {
            index: row.menu_index,
            name: row.name.clone(),
            provider: row.provider.clone(),
            windows: row.windows.clone(),
            detail: row.detail.clone(),
        })
        .collect();
    crate::mac_cell::apply(menu.ns_menu(), &cells);
}

/// Watch the menu the status item is actually showing, after it has been set.
///
/// The ordering is the whole fix. `tray-icon`'s `set_menu` ends with
/// `setDelegate: ns_status_item`, so a delegate installed before it is silently
/// replaced — which is what happened: the companion set one, `set_menu` threw
/// it away on the same call, and no menu-open signal ever arrived. Nothing
/// reported an error; the badge simply never cleared.
#[cfg(target_os = "macos")]
fn observe_menu(tray: &TrayIcon) {
    use objc2::rc::Retained;
    use objc2::MainThreadMarker;

    let (Some(item), Some(mtm)) = (tray.ns_status_item(), MainThreadMarker::new()) else {
        crate::mac_menu_open::trace("no status item to watch");
        return;
    };
    let Some(menu) = item.menu(mtm) else {
        crate::mac_menu_open::trace("the status item carries no menu");
        return;
    };
    crate::mac_menu_open::observe(Retained::as_ptr(&menu) as *mut std::ffi::c_void);
}

#[cfg(not(target_os = "macos"))]
fn observe_menu(_tray: &TrayIcon) {}

#[cfg(not(target_os = "macos"))]
fn style_rows(_menu: &Menu, _rows: &[crate::runner::Row]) {}

pub fn build_menu(entries: &[Entry]) -> Result<(Menu, HashMap<MenuId, ActionId>), muda::Error> {
    let menu = Menu::new();
    let mut actions = HashMap::new();
    append_entries(&menu, entries, &mut actions)?;
    Ok((menu, actions))
}

/// Append entries to any menu, root or submenu.
///
/// One level of nesting is all the model can express, so this recurses without
/// a depth guard: a `Submenu` containing a `Submenu` is not something the menu
/// builder can produce.
fn append_entries(
    menu: &dyn Appendable,
    entries: &[Entry],
    actions: &mut HashMap<MenuId, ActionId>,
) -> Result<(), muda::Error> {
    for entry in entries {
        match entry {
            Entry::Info(text) => {
                let item = MenuItem::new(text, false, None);
                menu.add(&item)?;
            }
            Entry::Check { id, label, checked } => {
                let item = CheckMenuItem::new(label, true, *checked, None);
                actions.insert(item.id().clone(), id.clone());
                menu.add(&item)?;
            }
            Entry::Separator => menu.add(&PredefinedMenuItem::separator())?,
            Entry::Action { id, label, enabled } => {
                let item = MenuItem::new(label, *enabled, None);
                actions.insert(item.id().clone(), id.clone());
                menu.add(&item)?;
            }
            Entry::Submenu { label, items, .. } => {
                // The parent carries no action of its own: opening it is the
                // click, and every action lives inside. `about` is what binds
                // the drawn macOS cell to it, not something muda needs.
                let submenu = Submenu::new(label, true);
                append_entries(&submenu, items, actions)?;
                menu.add(&submenu)?;
            }
        }
    }
    Ok(())
}

/// Appending is the only thing this needs from a menu, and `Menu` and `Submenu`
/// do not share a trait that offers it.
trait Appendable {
    fn add(&self, item: &dyn muda::IsMenuItem) -> Result<(), muda::Error>;
}

impl Appendable for Menu {
    fn add(&self, item: &dyn muda::IsMenuItem) -> Result<(), muda::Error> {
        self.append(item)
    }
}

impl Appendable for Submenu {
    fn add(&self, item: &dyn muda::IsMenuItem) -> Result<(), muda::Error> {
        self.append(item)
    }
}

/// Update the status item in place.
///
/// Rebuilding the `TrayIcon` instead would briefly own two status items, since
/// the replacement is created before the old one drops, and the icon visibly
/// jumps along the menu bar on every refresh. That is once every 30 seconds,
/// forever, so it has to be a mutation rather than a rebuild.
/// The marker beside the glyph, set on its own.
///
/// Needed because the first draw happens before the loop: alerts already
/// waiting when the companion starts would otherwise show no marker until the
/// next poll, which is up to a minute of the icon saying nothing happened.
///
/// Clearing it is not symmetrical with setting it, and that asymmetry was a
/// bug for as long as this file has existed: `tray-icon`'s macOS `set_title`
/// is `if let Some(title) = title { button.setTitle(...) }` — a `None` does
/// nothing at all. So the marker could be raised and never lowered. The
/// 45-second expiry it replaced never worked either; nobody noticed, because
/// a marker that outstays its welcome looks like a marker that is still true.
pub fn set_title(tray: &TrayIcon, title: Option<String>) {
    match title {
        Some(text) => tray.set_title(Some(text)),
        None => clear_title(tray),
    }
}

/// Empty the status item's own button title, since the crate will not.
#[cfg(target_os = "macos")]
fn clear_title(tray: &TrayIcon) {
    use objc2::MainThreadMarker;
    use objc2_foundation::NSString;

    let (Some(item), Some(mtm)) = (tray.ns_status_item(), MainThreadMarker::new()) else {
        return;
    };
    if let Some(button) = item.button(mtm) {
        button.setTitle(&NSString::from_str(""));
    }
}

/// Everywhere else `None` means what it says.
#[cfg(not(target_os = "macos"))]
fn clear_title(tray: &TrayIcon) {
    tray.set_title(None::<String>);
}

pub fn update_tray(
    tray: &TrayIcon,
    state: &str,
    tooltip: &str,
    title: Option<String>,
    entries: &[Entry],
    rows: &[crate::runner::Row],
) -> Result<HashMap<MenuId, ActionId>, String> {
    let (menu, actions) = build_menu(entries).map_err(|e| e.to_string())?;
    style_rows(&menu, rows);
    tray.set_menu(Some(Box::new(menu)));
    observe_menu(tray);
    let _ = tray.set_tooltip(Some(tooltip));
    // Beside the glyph, never instead of it: the glyph means remaining quota,
    // and replacing it with an alert marker would hide the one thing the icon
    // exists to show. `None` clears it, which is what makes the marker temporary.
    set_title(tray, title);
    tray.set_icon(Some(icon_for(state)?))
        .map_err(|e| e.to_string())?;
    // Re-asserted after every set_icon, and this is not belt-and-braces.
    // tray-icon's macOS set_icon passes is_template: false unconditionally, so
    // it silently clears what the builder was told. The symptom is an icon that
    // starts white and turns black at the first poll — invisible on a dark menu
    // bar, thirty seconds after launch, which is why it looked fine in testing.
    tray.set_icon_as_template(!wants_light_glyph());
    Ok(actions)
}

pub fn build_tray(
    state: &str,
    tooltip: &str,
    entries: &[Entry],
    rows: &[crate::runner::Row],
) -> Result<(TrayIcon, HashMap<MenuId, ActionId>), String> {
    let (menu, actions) = build_menu(entries).map_err(|e| e.to_string())?;
    style_rows(&menu, rows);
    let tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_icon(icon_for(state)?)
        // macOS-only: it is what makes macOS invert the black glyph per theme.
        // Windows ignores it, which is why Windows picks its colour instead.
        .with_icon_as_template(!wants_light_glyph())
        .with_tooltip(tooltip)
        .build()
        .map_err(|e| e.to_string())?;
    observe_menu(&tray);
    Ok((tray, actions))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_state_has_a_glyph_and_unknown_is_the_fallback() {
        for state in ["ok", "low", "critical", "unknown"] {
            assert!(!glyph_bytes(state, false).is_empty(), "{state}");
            assert!(!glyph_bytes(state, true).is_empty(), "{state} light");
        }
        // A state invented by a newer CDX must still render something.
        assert_eq!(
            glyph_bytes("teleporting", false),
            glyph_bytes("unknown", false)
        );
        assert_eq!(
            glyph_bytes("teleporting", true),
            glyph_bytes("unknown", true)
        );
        assert_ne!(glyph_bytes("ok", false), glyph_bytes("critical", false));
        // The two colourways must differ, or Windows would show the invisible one.
        assert_ne!(glyph_bytes("ok", false), glyph_bytes("ok", true));
    }

    #[test]
    fn the_glyphs_decode_at_their_intended_size() {
        for state in ["ok", "low", "critical", "unknown"] {
            let (rgba, w, h) = image_from_png(glyph_bytes(state, false)).expect(state);
            assert_eq!((w, h), (18, 18), "{state}");
            assert_eq!(rgba.len(), (w * h * 4) as usize, "{state}");
        }
    }

    #[test]
    fn the_glyphs_are_black_on_transparency() {
        // A template image must be black plus alpha. A stray colour or an
        // opaque background would defeat the menu bar's theme inversion.
        let (rgba, _, _) = image_from_png(glyph_bytes("critical", false)).unwrap();
        let mut opaque_pixels = 0;
        for px in rgba.chunks_exact(4) {
            if px[3] > 0 {
                opaque_pixels += 1;
                assert_eq!((px[0], px[1], px[2]), (0, 0, 0), "glyph must be pure black");
            }
        }
        assert!(opaque_pixels > 0, "the glyph must draw something");
    }
}
