//! Native notification delivery on macOS, with an honest fallback.
//!
//! `req_038` wants alerts to come from the signed CDX bundle so they carry the
//! CDX name and icon, and so a user can turn them off in System Settings under
//! CDX rather than under whatever script delivered them.
//!
//! Two hard constraints shape this:
//!
//!   - `UNUserNotificationCenter` **raises** when the running process has no
//!     bundle identifier. A development build run as a bare binary is exactly
//!     that, so the identifier is checked before the framework is touched. This
//!     is not defensive programming; without it the companion dies the first
//!     time an agent finishes a turn.
//!   - Authorization can be refused, revoked in System Settings, or never
//!     granted. None of those is an error worth losing an alert over, so
//!     delivery falls back to `osascript`, which shows a banner attributed to
//!     Script Editor — worse, and far better than silence.
//!
//! Exactly one of the two paths runs. A fallback that fired alongside a
//! successful native post would double every alert the tray was built to
//! de-duplicate.

#[cfg(target_os = "macos")]
mod imp {
    use objc2::msg_send;
    use objc2::rc::Retained;
    use objc2::runtime::AnyClass;
    use objc2_foundation::{NSBundle, NSString};

    /// What the system will let us do right now.
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum Authorization {
        /// The framework is reachable and has said yes.
        Granted,
        /// Reachable, and the user said no or revoked it.
        Denied,
        /// Asked but not yet answered by the user.
        NotDetermined,
        /// No bundle identifier, or the framework is not present. Reported
        /// rather than guessed: it is the state a development build is in, and
        /// telling it apart from a refusal is what makes the report useful.
        Unavailable,
    }

    impl Authorization {
        pub fn as_str(self) -> &'static str {
            match self {
                Authorization::Granted => "granted",
                Authorization::Denied => "denied",
                Authorization::NotDetermined => "not determined",
                Authorization::Unavailable => "unavailable",
            }
        }
    }

    /// Whether this process is a bundle at all.
    ///
    /// Everything below depends on it: `UNUserNotificationCenter` raises an
    /// exception for a process without a bundle identifier rather than
    /// returning an error, and an exception here would take the companion down
    /// on the first agent alert.
    pub fn bundle_identifier() -> Option<String> {
        unsafe {
            let bundle = NSBundle::mainBundle();
            let identifier: Option<Retained<NSString>> = msg_send![&*bundle, bundleIdentifier];
            identifier.map(|value| value.to_string())
        }
    }

    fn center() -> Option<Retained<objc2::runtime::AnyObject>> {
        bundle_identifier()?;
        let class = AnyClass::get(c"UNUserNotificationCenter")?;
        unsafe {
            let center: Option<Retained<objc2::runtime::AnyObject>> =
                msg_send![class, currentNotificationCenter];
            center
        }
    }

    /// Ask once, at startup. The answer arrives asynchronously and is not
    /// waited on: the first alert may therefore fall back, and the second will
    /// not. Blocking a menu bar app's startup on a permission dialog would be
    /// the worse trade.
    pub fn request_authorization() {
        let Some(center) = center() else { return };
        // Alert | Sound. Badge is deliberately not requested: a count on an app
        // with no Dock icon is meaningless.
        let options: usize = (1 << 2) | (1 << 1);
        unsafe {
            let block = block2::RcBlock::new(
                |_granted: objc2::runtime::Bool, _error: *mut objc2::runtime::AnyObject| {},
            );
            let _: () = msg_send![
                &*center,
                requestAuthorizationWithOptions: options,
                completionHandler: &*block,
            ];
        }
    }

    /// Post through the bundle. `Err` means the caller should fall back.
    pub fn post(title: &str, body: &str, identifier: &str) -> Result<(), String> {
        let center = center().ok_or_else(|| "not running from a bundle".to_string())?;
        let content_class = AnyClass::get(c"UNMutableNotificationContent")
            .ok_or_else(|| "UserNotifications is unavailable".to_string())?;
        let request_class = AnyClass::get(c"UNNotificationRequest")
            .ok_or_else(|| "UserNotifications is unavailable".to_string())?;

        unsafe {
            let content: Retained<objc2::runtime::AnyObject> = msg_send![content_class, new];
            let ns_title = NSString::from_str(title);
            let ns_body = NSString::from_str(body);
            let _: () = msg_send![&*content, setTitle: &*ns_title];
            let _: () = msg_send![&*content, setBody: &*ns_body];

            let ns_id = NSString::from_str(identifier);
            let request: Retained<objc2::runtime::AnyObject> = msg_send![
                request_class,
                requestWithIdentifier: &*ns_id,
                content: &*content,
                trigger: std::ptr::null::<objc2::runtime::AnyObject>(),
            ];
            let block = block2::RcBlock::new(|_error: *mut objc2::runtime::AnyObject| {});
            let _: () = msg_send![
                &*center,
                addNotificationRequest: &*request,
                withCompletionHandler: &*block,
            ];
        }
        Ok(())
    }

    /// The real authorization state, asked of the system.
    ///
    /// `getNotificationSettings` answers on a background queue, so the block
    /// hands the value back through a channel and this waits briefly for it.
    /// Reporting "granted" merely because the framework was reachable would be
    /// the dishonest version: reachable says nothing about what the user chose,
    /// and the whole point of a diagnostic is that it does not guess.
    pub fn authorization() -> Authorization {
        let Some(center) = center() else {
            return Authorization::Unavailable;
        };
        let (sender, receiver) = std::sync::mpsc::channel::<isize>();
        unsafe {
            let block = block2::RcBlock::new(move |settings: *mut objc2::runtime::AnyObject| {
                if settings.is_null() {
                    let _ = sender.send(-1);
                    return;
                }
                let status: isize = msg_send![settings, authorizationStatus];
                let _ = sender.send(status);
            });
            let _: () = msg_send![&*center, getNotificationSettingsWithCompletionHandler: &*block];
        }
        // Bounded: a diagnostic that hangs is worse than one that says it does
        // not know.
        match receiver.recv_timeout(std::time::Duration::from_secs(2)) {
            // 0 notDetermined, 1 denied, 2 authorized, 3 provisional, 4 ephemeral.
            Ok(0) => Authorization::NotDetermined,
            Ok(1) => Authorization::Denied,
            Ok(2) | Ok(3) | Ok(4) => Authorization::Granted,
            _ => Authorization::Unavailable,
        }
    }
}

#[cfg(not(target_os = "macos"))]
mod imp {
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub enum Authorization {
        Granted,
        Denied,
        NotDetermined,
        Unavailable,
    }

    impl Authorization {
        pub fn as_str(self) -> &'static str {
            "unavailable"
        }
    }

    pub fn bundle_identifier() -> Option<String> {
        None
    }
    pub fn request_authorization() {}
    pub fn post(_title: &str, _body: &str, _identifier: &str) -> Result<(), String> {
        Err("no native notification path on this platform".into())
    }
    pub fn authorization() -> Authorization {
        Authorization::Unavailable
    }
}

pub use imp::{authorization, bundle_identifier, request_authorization};

/// Deliver one alert, natively if we can and through `osascript` if we cannot.
///
/// Exactly one path runs. Firing the fallback after a successful native post
/// would double every alert, which is the failure the whole tray handoff exists
/// to prevent.
pub fn deliver(title: &str, body: &str, identifier: &str) {
    // Authorization is checked first because `addNotificationRequest` succeeds
    // whether or not the user ever granted it: the request is accepted and the
    // banner is silently dropped. Trusting its result would mean believing an
    // alert was delivered every time, and never falling back — the one failure
    // mode that loses notifications outright.
    if imp::authorization() == imp::Authorization::Granted
        && imp::post(title, body, identifier).is_ok()
    {
        return;
    }
    fallback(title, body);
}

/// The last resort. Attributed to Script Editor rather than to CDX, which is
/// why it is not the primary path — but a banner the user sees beats a correct
/// one they never do.
#[cfg(target_os = "macos")]
fn fallback(title: &str, body: &str) {
    let script = format!(
        "display notification {} with title {}",
        applescript_string(body),
        applescript_string(title)
    );
    let _ = std::process::Command::new("osascript")
        .args(["-e", &script])
        .status();
}

#[cfg(not(target_os = "macos"))]
fn fallback(_title: &str, _body: &str) {}

/// Quote for AppleScript, which understands only `\\` and `"` escapes.
///
/// Session names and repository names reach this, and a quotation mark in one
/// would otherwise end the string and turn the rest into script.
#[cfg(target_os = "macos")]
fn applescript_string(value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace('"', "\\\"");
    format!("\"{escaped}\"")
}

#[cfg(test)]
#[cfg(target_os = "macos")]
mod tests {
    use super::*;

    #[test]
    fn a_quote_cannot_escape_the_applescript_string() {
        assert_eq!(
            applescript_string(r#"say "hi" \ now"#),
            r#""say \"hi\" \\ now""#
        );
    }

    #[test]
    fn a_bare_binary_reports_unavailable_rather_than_crashing() {
        // The test binary is not a bundle, which is exactly the development
        // case the bundle-identifier guard exists for. Reaching
        // UNUserNotificationCenter here would raise rather than return.
        assert_eq!(imp::authorization(), imp::Authorization::Unavailable);
        assert!(imp::post("t", "b", "id").is_err());
    }
}
