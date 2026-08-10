//! The native tray backend: entries in, menu bar out.
//!
//! Everything decided elsewhere. This module owns no policy — it turns
//! `menu::Entry` values into `muda` items, picks the glyph for a state, and
//! runs the platform event loop. Keeping it that thin is what lets the menu
//! model and the poll cadence be tested without a windowing session.

use std::collections::HashMap;

use muda::{Menu, MenuId, MenuItem, PredefinedMenuItem};
use tray_icon::{Icon, TrayIcon, TrayIconBuilder};

use crate::menu::{ActionId, Entry};

/// The glyphs, compiled in. They are a few hundred bytes each and the companion
/// must render an icon before it can report that anything is wrong, so a
/// missing file on disk is not a failure mode worth having.
const GLYPH_OK: &[u8] = include_bytes!("../assets/macos/CDXTemplate-ok.png");
const GLYPH_LOW: &[u8] = include_bytes!("../assets/macos/CDXTemplate-low.png");
const GLYPH_CRITICAL: &[u8] = include_bytes!("../assets/macos/CDXTemplate-critical.png");
const GLYPH_UNKNOWN: &[u8] = include_bytes!("../assets/macos/CDXTemplate-unknown.png");

pub fn glyph_bytes(state: &str) -> &'static [u8] {
    match state {
        "ok" => GLYPH_OK,
        "low" => GLYPH_LOW,
        "critical" => GLYPH_CRITICAL,
        // Anything unrecognised, including a state a newer CDX invented, shows
        // the unknown glyph rather than no icon at all.
        _ => GLYPH_UNKNOWN,
    }
}

fn icon_for(state: &str) -> Result<Icon, String> {
    let bytes = glyph_bytes(state);
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
pub fn build_menu(entries: &[Entry]) -> Result<(Menu, HashMap<MenuId, ActionId>), muda::Error> {
    let menu = Menu::new();
    let mut actions = HashMap::new();
    for entry in entries {
        match entry {
            Entry::Info(text) => {
                let item = MenuItem::new(text, false, None);
                menu.append(&item)?;
            }
            Entry::Separator => menu.append(&PredefinedMenuItem::separator())?,
            Entry::Action { id, label, enabled } => {
                let item = MenuItem::new(label, *enabled, None);
                actions.insert(item.id().clone(), *id);
                menu.append(&item)?;
            }
        }
    }
    Ok((menu, actions))
}

pub fn build_tray(
    state: &str,
    entries: &[Entry],
) -> Result<(TrayIcon, HashMap<MenuId, ActionId>), String> {
    let (menu, actions) = build_menu(entries).map_err(|e| e.to_string())?;
    let tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_icon(icon_for(state)?)
        // The template flag is what makes macOS invert the glyph for the
        // current menu bar theme. Without it the icon is black on black.
        .with_icon_as_template(true)
        .with_tooltip("CDX")
        .build()
        .map_err(|e| e.to_string())?;
    Ok((tray, actions))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_state_has_a_glyph_and_unknown_is_the_fallback() {
        for state in ["ok", "low", "critical", "unknown"] {
            assert!(!glyph_bytes(state).is_empty(), "{state}");
        }
        // A state invented by a newer CDX must still render something.
        assert_eq!(glyph_bytes("teleporting"), glyph_bytes("unknown"));
        assert_ne!(glyph_bytes("ok"), glyph_bytes("critical"));
    }

    #[test]
    fn the_glyphs_decode_at_their_intended_size() {
        for state in ["ok", "low", "critical", "unknown"] {
            let (rgba, w, h) = image_from_png(glyph_bytes(state)).expect(state);
            assert_eq!((w, h), (18, 18), "{state}");
            assert_eq!(rgba.len(), (w * h * 4) as usize, "{state}");
        }
    }

    #[test]
    fn the_glyphs_are_black_on_transparency() {
        // A template image must be black plus alpha. A stray colour or an
        // opaque background would defeat the menu bar's theme inversion.
        let (rgba, _, _) = image_from_png(glyph_bytes("critical")).unwrap();
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
