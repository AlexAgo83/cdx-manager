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

use std::cell::Cell as StateCell;

use objc2::rc::Retained;
use objc2::runtime::NSObjectProtocol;
use objc2::{define_class, msg_send, DefinedClass, MainThreadMarker, MainThreadOnly};
use objc2_app_kit::{
    NSAutoresizingMaskOptions, NSBox, NSBoxType, NSColor, NSFont, NSMenu, NSMenuItem, NSRectFill,
    NSTextAlignment, NSTextField, NSTitlePosition, NSView,
};
use objc2_foundation::{NSPoint, NSRect, NSSize, NSString};

define_class!(
    /// The row's own view, which has to draw its own selection.
    ///
    /// An `NSMenuItem` carrying a view draws none of its standard furniture, and
    /// the highlight is the half of that a user notices immediately: every other
    /// item in the menu lights up under the pointer and these did not, which
    /// reads as a row that cannot be clicked.
    ///
    /// The item's own `highlighted` property is not the signal. Since Big Sur it
    /// stays true after the drawn row has visually stopped being highlighted, so
    /// the menu delegate is what says which row is current.
    #[unsafe(super(NSView))]
    #[name = "CdxRowView"]
    #[thread_kind = MainThreadOnly]
    #[ivars = StateCell<bool>]
    struct RowView;

    unsafe impl NSObjectProtocol for RowView {}

    impl RowView {
        #[unsafe(method(drawRect:))]
        fn draw_rect(&self, _dirty: NSRect) {
            if !self.ivars().get() {
                return;
            }
            // The unemphasized selection colour rather than the accent one: it
            // is the pair AppKit keeps legible against ordinary label colours in
            // both menu materials, so the row lights up without every label
            // having to be repainted white.
            NSColor::unemphasizedSelectedContentBackgroundColor().setFill();
            NSRectFill(self.bounds());
        }
    }
);

impl RowView {
    fn new(frame: NSRect, mtm: MainThreadMarker) -> Retained<Self> {
        let this = mtm.alloc::<Self>().set_ivars(StateCell::new(false));
        unsafe { msg_send![super(this), initWithFrame: frame] }
    }

    fn set_highlighted(&self, highlighted: bool) {
        if self.ivars().get() == highlighted {
            return;
        }
        self.ivars().set(highlighted);
        self.setNeedsDisplay(true);
    }
}

/// Move the highlight to the row the menu says is current.
///
/// Called from the menu delegate, which is the only thing that knows. Every
/// drawn row is cleared and at most one is set, so a pointer leaving the menu
/// entirely — `item` is None — leaves nothing lit.
pub fn highlight(ns_menu: &NSMenu, item: Option<&NSMenuItem>) {
    for index in 0..ns_menu.numberOfItems() {
        let Some(row) = ns_menu.itemAtIndex(index) else {
            continue;
        };
        let Some(view) = row.view() else {
            continue;
        };
        let Ok(drawn) = view.downcast::<RowView>() else {
            continue;
        };
        let current = item.is_some_and(|highlighted| std::ptr::eq(highlighted, &*row));
        drawn.set_highlighted(current);
    }
}

/// What one row needs to draw itself.
pub struct Cell {
    /// Position of the row in the menu, matching the entry list it was built from.
    pub index: usize,
    pub name: String,
    /// A view replaces the label entirely, so a provider that is not drawn here
    /// is a provider the macOS user cannot read anywhere. The text rows the
    /// other backends keep say it on the same line.
    pub provider: String,
    /// One entry per reported window — five hours, a week — each drawn on its
    /// own line with its own bar and its own name. `None` draws an empty bar
    /// rather than a full one, because a session that never reported must not
    /// look healthy at a glance. Two numbers on one line
    /// would need colour or position to tell them apart; a line each needs
    /// neither, which is what keeps it readable without relying on colour.
    pub windows: Vec<(String, Option<f64>)>,
    /// The second line: how old the figure is, and when it resets. Both were
    /// missing from this cell entirely — the text rows on the other platforms
    /// said them, and macOS, which is the platform that draws, said neither.
    pub detail: String,
}

/// Two lines: the name and the figure on top, how much to trust it underneath.
///
/// One line could not hold both. The first already carries a name, a provider,
/// a gauge, a figure and a chevron across 260 points, and squeezing an age and
/// a reset in beside them would have shortened the name — which is the one
/// thing on the row that identifies the session.
const ROW_HEIGHT: f64 = 34.0;
const TOP_LINE_Y: f64 = 17.0;
const TOP_LINE_HEIGHT: f64 = 15.0;
const DETAIL_Y: f64 = 3.0;
const DETAIL_HEIGHT: f64 = 13.0;
/// Wide enough for what the row actually says.
///
/// 260 was the width of a row carrying a name and a figure. It now carries a
/// name, a provider, an age, a reset and two named windows, and at 260 the
/// first screenshot of it showed "claud", "antigr" and a reset cut mid-word.
/// A menu sizes itself to its widest item, so this costs nothing on a menu that
/// already holds a sentence like "Refresh unavailable while a session is
/// running".
const ROW_WIDTH: f64 = 340.0;
const GAUGE_WIDTH: f64 = 46.0;
const GAUGE_HEIGHT: f64 = 4.0;
/// Wide enough for "wk 100%", because the window's name travels with its
/// figure: a bare percentage would leave the two lines indistinguishable. The
/// first attempt at 54 truncated exactly the value it needed to show — a full
/// week — into "wk 100…".
const FIGURE_WIDTH: f64 = 68.0;
const INSET_LEFT: f64 = 14.0;
const INSET_RIGHT: f64 = 12.0;
/// Room for the submenu chevron at the right edge.
///
/// Drawn by hand because it has to be: an `NSMenuItem` carrying a view draws
/// none of its standard furniture — no title, no state, no highlight and no
/// submenu arrow — so a row that opens into actions would otherwise look
/// exactly like one that does nothing.
const CHEVRON_WIDTH: f64 = 14.0;
/// How much of the text column the session name takes, leaving the rest to the
/// provider. Session names are what the user reads first and are the longer of
/// the two; a provider is one short word from a set of two.
const NAME_SHARE: f64 = 0.62;

/// A percentage, or the same em dash the text rows use for a session that has
/// never reported: an empty column would read as a rendering fault.
fn percent_text(value: Option<f64>) -> String {
    match value {
        Some(v) => format!("{}%", v.round() as i64),
        None => "—".to_string(),
    }
}

/// The colour of one window's bar.
///
/// Identity first: the five-hour window is yellow and the week is green, so two
/// bars on one row are told apart without reading the labels beside them. That
/// is what the operator asked for, and it is the right default — the two
/// windows are different questions, not two readings of one.
///
/// Severity still wins when it matters. A window below the thresholds the icon
/// uses turns orange or red whichever window it is, because a bar that stayed
/// yellow at four percent would be using colour to say "five hours" at the one
/// moment it needs to say "about to run out". The figure beside it says the
/// number either way, so no state is carried by colour alone.
fn window_colour(name: &str, value: Option<f64>) -> Retained<NSColor> {
    // The thresholds come from the same function the icon state does, rather
    // than being restated here: two copies of "low means under 25" is how a bar
    // and a glyph end up disagreeing about the same session.
    match crate::menu::state_for(value) {
        "critical" => NSColor::systemRedColor(),
        "low" => NSColor::systemOrangeColor(),
        "unknown" => NSColor::tertiaryLabelColor(),
        _ if name == "5h" => NSColor::systemYellowColor(),
        _ => NSColor::systemGreenColor(),
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
    // An ellipsis rather than a clean cut. A label that runs out of room ends
    // in "claud" and reads as a bug in the data; ending in "clau…" reads as a
    // narrow column, which is what it is. Belt and braces behind the width
    // above: a long session name is the user's to choose, not ours to bound.
    if let Some(cell) = field.cell() {
        cell.setUsesSingleLineMode(true);
        cell.setLineBreakMode(objc2_app_kit::NSLineBreakMode::ByTruncatingTail);
    }
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
    let container = RowView::new(
        NSRect::new(NSPoint::new(0.0, 0.0), NSSize::new(ROW_WIDTH, ROW_HEIGHT)),
        mtm,
    );
    container.setAutoresizingMask(NSAutoresizingMaskOptions::ViewWidthSizable);

    let figure_x = ROW_WIDTH - INSET_RIGHT - CHEVRON_WIDTH - FIGURE_WIDTH;
    let gauge_x = figure_x - 8.0 - GAUGE_WIDTH;
    let top = |height: f64| NSPoint::new(0.0, TOP_LINE_Y + (TOP_LINE_HEIGHT - height) / 2.0);

    // Name, on the left, in the menu's own weight. The provider follows it in
    // the secondary colour and a smaller size: it is what distinguishes two
    // accounts with similar names, but it is not what the row is about, and the
    // list is short enough that a column of its own would be width wasted.
    let text_width = gauge_x - INSET_LEFT - 8.0;
    let name = label(&cell.name, 13.0, NSColor::labelColor(), mtm);
    name.setFrame(NSRect::new(
        NSPoint::new(INSET_LEFT, top(TOP_LINE_HEIGHT).y),
        NSSize::new(text_width * NAME_SHARE, TOP_LINE_HEIGHT),
    ));
    container.addSubview(&name);

    let provider = label(&cell.provider, 11.0, NSColor::secondaryLabelColor(), mtm);
    provider.setFrame(NSRect::new(
        NSPoint::new(
            INSET_LEFT + text_width * NAME_SHARE,
            top(TOP_LINE_HEIGHT - 1.0).y,
        ),
        NSSize::new(text_width * (1.0 - NAME_SHARE), TOP_LINE_HEIGHT - 1.0),
    ));
    container.addSubview(&provider);

    // One window per line, each with its own bar and its own name. The lines
    // are the two the row already has, so a second window costs no height.
    for (index, (name, value)) in cell.windows.iter().take(2).enumerate() {
        let line_y = if index == 0 { TOP_LINE_Y } else { DETAIL_Y };
        let line_height = if index == 0 {
            TOP_LINE_HEIGHT
        } else {
            DETAIL_HEIGHT
        };
        let track_y = line_y + (line_height - GAUGE_HEIGHT) / 2.0;

        // The track, then the fill over it. Drawn as two layers rather than one
        // gradient so an empty gauge still shows where full would be.
        let track = bar(
            NSRect::new(
                NSPoint::new(gauge_x, track_y),
                NSSize::new(GAUGE_WIDTH, GAUGE_HEIGHT),
            ),
            &NSColor::quaternaryLabelColor(),
            mtm,
        );
        container.addSubview(&track);

        let filled = value.unwrap_or(0.0).clamp(0.0, 100.0) / 100.0 * GAUGE_WIDTH;
        if filled > 0.5 {
            let fill = bar(
                NSRect::new(
                    NSPoint::new(gauge_x, track_y),
                    NSSize::new(filled, GAUGE_HEIGHT),
                ),
                &window_colour(name, *value),
                mtm,
            );
            container.addSubview(&fill);
        }

        // The figure, on its own column so the digits line up down the menu,
        // carrying the window's name so the two lines cannot be confused.
        let text = if name.is_empty() {
            percent_text(*value)
        } else {
            format!("{name} {}", percent_text(*value))
        };
        let size = if index == 0 { 12.0 } else { 11.0 };
        let figure = label(&text, size, NSColor::secondaryLabelColor(), mtm);
        figure.setAlignment(NSTextAlignment::Right);
        figure.setFrame(NSRect::new(
            NSPoint::new(figure_x, line_y),
            NSSize::new(FIGURE_WIDTH, line_height),
        ));
        container.addSubview(&figure);
    }

    // The second line. Tertiary rather than secondary: it qualifies the figure
    // above rather than competing with it, and a row of thirteen sessions
    // should read as thirteen names with footnotes, not twenty-six lines.
    if !cell.detail.is_empty() {
        let detail = label(&cell.detail, 11.0, NSColor::tertiaryLabelColor(), mtm);
        detail.setFrame(NSRect::new(
            NSPoint::new(INSET_LEFT, DETAIL_Y),
            // Stops before the gauge column, which the second window now uses.
            NSSize::new(gauge_x - INSET_LEFT - 8.0, DETAIL_HEIGHT),
        ));
        container.addSubview(&detail);
    }

    // The chevron AppKit would have drawn if this row had kept its label.
    let chevron = label("\u{203a}", 13.0, NSColor::tertiaryLabelColor(), mtm);
    chevron.setAlignment(NSTextAlignment::Right);
    chevron.setFrame(NSRect::new(
        NSPoint::new(ROW_WIDTH - INSET_RIGHT - CHEVRON_WIDTH, 1.0),
        NSSize::new(CHEVRON_WIDTH, ROW_HEIGHT - 2.0),
    ));
    container.addSubview(&chevron);

    Retained::into_super(container)
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
