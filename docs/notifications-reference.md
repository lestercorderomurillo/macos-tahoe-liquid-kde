# Notification reference and qualification

The notification frontend replaces the notification frontend while retaining Plasma's
notification manager, history model, per-application exclusions, urgency,
actions, replies and job controls. It does not introduce another tray manager.
Bluetooth, brightness and volume controls are removed from themed trays;
the existing Control Center remains their entry point. Third-party status
items and unrelated panels retain their configuration.

## macOS references

- [Apple: View app notifications](https://support.apple.com/en-gb/guide/mac-help/mh40609/mac) shows the close disc outside the upper-left corner, exposed when hovering, and the Options control.
- [Apple: iPhone notifications on macOS Tahoe](https://support.apple.com/en-us/120684) supplies a Tahoe card reference. Its mirrored-device badge is specific to iPhone notifications and is not added to ordinary Linux notifications.
- [Apple: macOS 27 Safari Notify Me](https://www.apple.com/newsroom/2026/06/apple-unveils-next-generation-of-apple-intelligence-siri-ai-and-more/) supplies the separate Golden Gate reference and the text used for the measured comparison.
- The photographer's original [Tahoe](https://media.512pixels.net/downloads/macos-screenshots/26/26-Tahoe-Notification-Center.png) and [Golden Gate](https://media.512pixels.net/downloads/macos-screenshots/27/27-Golden-Gate-Notification-Center.png) screenshots supply separate Notification Center references. Their heading floats above individual glass cards, without an enclosing glass panel. Widgets are outside this candidate's scope.
- [Apple: Menu Bar settings](https://support.apple.com/guide/mac-help/change-menu-bar-settings-mchlad96d366/mac) distinguishes system controls from applications under “Allow in the Menu Bar.” This setting permits an application's status item; it does not describe a user-managed hidden-items drawer. The existing Plasma overflow remains available for Slack, Discord and similar applications. No new capsules or organizer are introduced in this change.

The reference crops are normalized to the same card width before comparing
positions. Measurements in logical pixels:

| Element | Candidate geometry |
| --- | --- |
| Card | 344 wide; 72 high for the reference's three text lines |
| Position | 16 from the right; 16 below the available desktop area, giving y=48 with the default 32px bar |
| Card radius | 20 |
| Text column | x=58; 13px SF Pro Display; 16px line spacing |
| App name and summary | Semibold; summary stays on one line |
| Description | Regular; two lines in a banner, full text in history |
| Icon | Original bundled artwork, centered beside the text block |
| Close disc | 20px; x=-6, y=-4 relative to the card; appears on hover |
| Close glyph | Original contours exported from the bundled Apple font |
| Options on hover | 78 × 22; 10px from the card's right and bottom; text elides without resizing the card |
| Consecutive cards | 6px gap |
| History heading | 18px SF Pro Display Semibold; aligned with the cards; approximately 12px between the heading's visible ink and the next card |
| History right margin | The same 16px as banners, independently of the bell's position |

SF Pro Display matches the line lengths in the contemporary reference more
closely than the bundled older SF Pro Text face. The latter wraps the reference
description onto an extra line at the same size. No unrelated component's font
is changed. Notification borders use a thinner existing glass rim; the default
rim on other Control Center tiles is unchanged.

The history retains application grouping and expand/collapse actions. Collapsed
groups show the newest message with two thin layers beneath it; incoming messages
refresh that preview. Options includes the existing notification settings even
when an application supplied no custom action. Native urgency, exclusions and
Do Not Disturb remain authoritative.

## Material and rendering

Banners and history use the saved Plasma-popup material, including edition,
mode, blur, refraction and opacity settings. They do not overwrite those
settings. Notification and critical-notification windows must be treated as
client surfaces by Acrylic Glass: their transparent gutter is not a server
frame, and the close disc must not create a second glass plate.

`notificationbanner.h` and `notificationbanner.cpp` adapt KDE's
[NotificationWindow](https://invent.kde.org/plasma/plasma-workspace/-/blob/Plasma/6.6/applets/notifications/notificationwindow.cpp).
David Edmundson's copyright and original SPDX alternatives remain in both files.

## Approval and limits

The user approved the actual corrected-chevron preview on 2026-11-17 before
paired release operations. The [approved Golden Gate hover](../src/screenshots/previews/notifications-golden-gate-hover-8908d4edf9c5.png)
is retained separately from the unchanged documentation galleries. Measured comparisons establish geometry and text layout;
they do not establish identical CoreText/Qt rasterization or identical pixels
under a different wallpaper. Existing bundled icon artwork is preserved.

Commands, source fingerprints, actual SDK coverage and limits are recorded in
the [qualification evidence](evidence/notifications-0735.json). The chevron is
exported deterministically from the bundled Apple font’s `uni100188.small`
contours; it is not a text character. Reviewed raw frames and logs are preserved
in the named local artifact backup identified by that evidence.
