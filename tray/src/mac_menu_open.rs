//! Seeing the macOS menu open.
//!
//! AppKit has both halves of the lifecycle — `menuWillOpen:` and
//! `menuDidClose:` — but `adr_006` takes only the opening, because Linux has no
//! closing signal and a marker that means different things per platform is
//! worse than one that means less.
//!
//! The delegate goes on the `NSMenu` muda hands over, and it replaces muda's
//! own. That delegate exists solely to carry a menu id for
//! `set_as_windows_menu_for_nsapp`, an API this companion never calls, so the
//! swap costs nothing today — but it is a coupling to a crate internal that no
//! public contract protects, which is why it is stated here and asserted in a
//! test rather than left to be discovered at the next `muda` bump.
//!
//! Nothing is cleared here. The delegate runs on the main thread inside
//! AppKit's own tracking, and the loop owns the unread state, so this raises a
//! flag and the loop drains it.

use std::sync::atomic::{AtomicBool, Ordering};

use objc2::rc::Retained;
use objc2::runtime::{NSObject, NSObjectProtocol, ProtocolObject};
use objc2::{define_class, msg_send, MainThreadMarker, MainThreadOnly};
use objc2_app_kit::{NSMenu, NSMenuDelegate};

static MENU_OPENED: AtomicBool = AtomicBool::new(false);
/// Whether the last attempt to watch a menu succeeded.
static INSTALLED: AtomicBool = AtomicBool::new(false);

define_class!(
    /// A delegate whose only job is to say the menu was shown.
    #[unsafe(super(NSObject))]
    #[name = "CdxMenuOpenDelegate"]
    #[thread_kind = MainThreadOnly]
    struct OpenDelegate;

    unsafe impl NSObjectProtocol for OpenDelegate {}

    unsafe impl NSMenuDelegate for OpenDelegate {
        #[unsafe(method(menuWillOpen:))]
        fn menu_will_open(&self, _menu: &NSMenu) {
            MENU_OPENED.store(true, Ordering::Relaxed);
        }
    }
);

/// The delegate has to outlive the menu it is set on: `setDelegate:` does not
/// retain, so a delegate dropped at the end of this function would leave the
/// menu calling into freed memory. One per process, kept forever, because there
/// is one status item and it is never torn down before exit.
fn delegate(mtm: MainThreadMarker) -> &'static ProtocolObject<dyn NSMenuDelegate> {
    use std::sync::OnceLock;
    static DELEGATE: OnceLock<usize> = OnceLock::new();
    let raw = *DELEGATE.get_or_init(|| {
        let object: Retained<OpenDelegate> =
            unsafe { msg_send![mtm.alloc::<OpenDelegate>(), init] };
        let protocol: &ProtocolObject<dyn NSMenuDelegate> = ProtocolObject::from_ref(&*object);
        let pointer = protocol as *const ProtocolObject<dyn NSMenuDelegate> as usize;
        std::mem::forget(object);
        pointer
    });
    // SAFETY: the delegate was leaked above precisely so this reference stays
    // valid for the life of the process.
    unsafe { &*(raw as *const ProtocolObject<dyn NSMenuDelegate>) }
}

/// Watch this menu for openings. Called after every draw, because the menu is
/// rebuilt on every redraw and the delegate goes with the new one.
///
/// Returns whether the delegate is in place. A false never clears anything,
/// which is the failing-closed behaviour `adr_006` requires.
pub fn observe(ns_menu: *mut std::ffi::c_void) -> bool {
    let Some(mtm) = MainThreadMarker::new() else {
        INSTALLED.store(false, Ordering::Relaxed);
        return false;
    };
    if ns_menu.is_null() {
        INSTALLED.store(false, Ordering::Relaxed);
        return false;
    }
    // SAFETY: the pointer comes from muda's `ContextMenu::ns_menu`, which
    // documents it as valid for as long as the menu it belongs to.
    let menu: &NSMenu = unsafe { &*(ns_menu as *const NSMenu) };
    menu.setDelegate(Some(delegate(mtm)));
    INSTALLED.store(true, Ordering::Relaxed);
    true
}

/// Whether the menu currently on the status item is being watched.
///
/// Read by the loop rather than threaded back through the backend's return
/// types: the menu is rebuilt on every redraw, and this is the state that
/// decides whether a consultation may clear anything.
pub fn installed() -> bool {
    INSTALLED.load(Ordering::Relaxed)
}

/// Whether the menu has been opened since this was last asked.
pub fn opened() -> bool {
    MENU_OPENED.swap(false, Ordering::Relaxed)
}
