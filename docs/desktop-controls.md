# Desktop controls

Control Center, Wi-Fi, Battery and Notifications use original project QML under
`org.kde.mac-tahoe-liquid-kde.*`. Their visual references are
[Apple’s macOS Tahoe Control Center](https://www.apple.com/newsroom/2025/06/macos-tahoe-26-makes-the-mac-more-capable-productive-and-intelligent-than-ever/)
and [macOS Golden Gate’s Liquid Glass refinements](https://www.apple.com/os/macos/).
No implementation is copied from the reviewed theme forks or MacShell.

The Control Center uses floating glass pills and circles, a media tile, slim
brightness and volume sliders, and saved visibility choices under Edit Controls.
Tahoe and Golden Gate retain their own material fills and effective light/dark
appearance. The shared native helper confines blur and pointer input to the
rounded controls; transparent gaps remain transparent.

Plasma provides the live NetworkManager, PowerDevil, PulseAudio/PipeWire, BlueZ,
MPRIS and notification models. Network credentials remain with the system
secret agent. The existing hidden Plasma notification service keeps ownership
of banners; the project menu supplies history, actions, replies and job controls.
Missing hardware is reported or disabled, never simulated.

New default layouts include all four applets. Existing customized panels remain
intact unless the user selects a layout reset; the applets can also be added
individually through Plasma’s widget chooser. Calendar remains last and the
existing clock/calendar is preserved in this delivery.

Validation and precise hardware/SDK coverage are recorded in
[release-evidence.json](../release-evidence.json). Historical README photographs
retain their original source and are not evidence for these new controls.

[Light preview](../src/screenshots/previews/control-center-tahoe-light-a595d01c855e.png) · [Dark preview](../src/screenshots/previews/control-center-tahoe-dark-8d2756c8f857.png) · [Capture provenance](../src/screenshots/previews/control-center-tahoe-provenance.json)
