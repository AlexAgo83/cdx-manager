//! Drawn rows for the macOS menu.
//!
//! A native menu gives you four things: text, a checkmark, a submenu, and an
//! image. Nothing aligns, because the menu font is proportional, so a table of
//! thirteen accounts arrives as thirteen ragged sentences. `NSMenuItem` has one
//! escape hatch — `setView:` — and this is it: a laid-out row with the name on
//! the left, a coloured gauge, and the figure right-aligned on a fixed column.
//!
//! Two constraints shaped what is here.
//!
//! It is macOS only, and deliberately so rather than by omission. Win32 would
//! need owner-draw, and a StatusNotifierItem menu is a D-Bus description that
//! carries a label and an icon and nothing else — there is no drawing to do on
//! Linux. The other two backends keep the text rows, which is why the text is
//! still generated for them and still says everything the drawing does.
//!
//! The text stays real text inside the view. Rendering the row to an image
//! would have been simpler and would have looked identical, and it would have
//! turned every state into pixels a screen reader cannot read and the system
//! font size cannot grow. `req_038` AC4 asks for the state in words; that rules
//! the image out.

use objc2::rc::Retained;
use objc2::MainThreadMarker;
use objc2_app_kit::{
    NSAutoresizingMaskOptions, NSBox, NSBoxType, NSColor, NSFont, NSMenu, NSTextAlignment,
    NSTextField, NSTitlePosition, NSView,
};
use objc2_foundation::{NSPoint, NSRect, NSSize, NSString};

/// What one row needs to draw itself.
pub struct Cell {
    /// Position of the row in the menu, matching the entry list it was built from.
    pub index: usize,
    pub name: String,
    /// `None` for a session that never reported: the gauge draws empty rather
    /// than full, because unknown must not look healthy at a glance.
    pub percent: Option<f64>,
    /// `ok`, `low`, `critical` or `unknown` — the same states the icon uses.
    pub state: String,
    /// The figure as text, so the number is never carried by the bar alone.
    pub figure: String,
}

const ROW_HEIGHT: f64 = 20.0;
const ROW_WIDTH: f64 = 260.0;
const GAUGE_WIDTH: f64 = 58.0;
const GAUGE_HEIGHT: f64 = 4.0;
const FIGURE_WIDTH: f64 = 38.0;
const INSET_LEFT: f64 = 14.0;
const INSET_RIGHT: f64 = 12.0;

fn severity_colour(state: &str) -> Retained<NSColor> {
    // Apple's own system colours rather than invented ones: they are the pair
    // that stays legible on both the light and the dark menu material, which a
    // hand-picked hex would have to be re-tuned for.
    match state {
        "critical" => NSColor::systemRedColor(),
        "low" => NSColor::systemOrangeColor(),
        "ok" => NSColor::systemGreenColor(),
        _ => NSColor::tertiaryLabelColor(),
    }
}

fn label(
    text: &str,
    size: f64,
    colour: Retained<NSColor>,
    mtm: MainThreadMarker,
) -> Retained<NSTextField> {
    let field = NSTextField::labelWithString(&NSString::from_str(text), mtm);
    field.setFont(Some(&NSFont::systemFontOfSize(size)));
    field.setTextColor(Some(&colour));
    field
}

/// A filled rectangle. `NSBox` rather than a layer-backed view: it takes a fill
/// colour directly, so the row needs no CALayer and no extra crate.
fn bar(frame: NSRect, colour: &NSColor, mtm: MainThreadMarker) -> Retained<NSBox> {
    let view = NSBox::initWithFrame(mtm.alloc::<NSBox>(), frame);
    view.setBoxType(NSBoxType::Custom);
    view.setTitlePosition(NSTitlePosition::NoTitle);
    view.setBorderWidth(0.0);
    view.setFillColor(colour);
    view
}

/// The view for one row, laid out in fixed columns.
pub fn build_cell(cell: &Cell, mtm: MainThreadMarker) -> Retained<NSView> {
    let container = NSView::initWithFrame(
        mtm.alloc::<NSView>(),
        NSRect::new(NSPoint::new(0.0, 0.0), NSSize::new(ROW_WIDTH, ROW_HEIGHT)),
    );
    container.setAutoresizingMask(NSAutoresizingMaskOptions::ViewWidthSizable);

    let gauge_x = ROW_WIDTH - INSET_RIGHT - FIGURE_WIDTH - 8.0 - GAUGE_WIDTH;

    // Name, on the left, in the menu's own weight.
    let name = label(&cell.name, 13.0, NSColor::labelColor(), mtm);
    name.setFrame(NSRect::new(
        NSPoint::new(INSET_LEFT, 1.0),
        NSSize::new(gauge_x - INSET_LEFT - 8.0, ROW_HEIGHT - 2.0),
    ));
    container.addSubview(&name);

    // The track, then the fill over it. Drawn as two layers rather than one
    // gradient so an empty gauge still shows where full would be.
    let track_y = (ROW_HEIGHT - GAUGE_HEIGHT) / 2.0;
    let track = bar(
        NSRect::new(
            NSPoint::new(gauge_x, track_y),
            NSSize::new(GAUGE_WIDTH, GAUGE_HEIGHT),
        ),
        &NSColor::quaternaryLabelColor(),
        mtm,
    );
    container.addSubview(&track);

    let filled = cell.percent.unwrap_or(0.0).clamp(0.0, 100.0) / 100.0 * GAUGE_WIDTH;
    if filled > 0.5 {
        let fill = bar(
            NSRect::new(
                NSPoint::new(gauge_x, track_y),
                NSSize::new(filled, GAUGE_HEIGHT),
            ),
            &severity_colour(&cell.state),
            mtm,
        );
        container.addSubview(&fill);
    }

    // The figure, on its own column so the digits line up down the menu.
    let figure = label(&cell.figure, 12.0, NSColor::secondaryLabelColor(), mtm);
    figure.setAlignment(NSTextAlignment::Right);
    figure.setFrame(NSRect::new(
        NSPoint::new(ROW_WIDTH - INSET_RIGHT - FIGURE_WIDTH, 1.0),
        NSSize::new(FIGURE_WIDTH, ROW_HEIGHT - 2.0),
    ));
    container.addSubview(&figure);

    container
}

/// Attach a drawn row to every session item in a menu.
///
/// The menu is muda's, reached through the pointer it exposes, and the indices
/// come from the entry list it was built from — the two are in the same order
/// by construction. Anything unexpected is left as text: a row that failed to
/// gain a view is a plain menu row, which is the state this replaced.
pub fn apply(ns_menu: *mut std::ffi::c_void, cells: &[Cell]) {
    let Some(mtm) = MainThreadMarker::new() else {
        return;
    };
    if ns_menu.is_null() {
        return;
    }
    let menu: &NSMenu = unsafe { &*(ns_menu as *const NSMenu) };
    let count = menu.numberOfItems();
    for cell in cells {
        if cell.index as isize >= count {
            continue;
        }
        let Some(item) = menu.itemAtIndex(cell.index as isize) else {
            continue;
        };
        item.setView(Some(&build_cell(cell, mtm)));
    }
}
