// MacTahoe Liquid KDE — macOS Tahoe-style layout
// Top menu bar (flush) + bottom dock (floating, large icons)
// Applied per-screen so multi-monitor setups get a matching bar + dock on
// every display, not just the primary one.

// ── remove existing panels ──────────────────────
var old = panels();
for (var i = 0; i < old.length; i++) {
    old[i].remove();
}

for (var screen = 0; screen < screenCount; screen++) {
    // ── top menu bar ────────────────────────────────
    // Top bar, flush panel with applets-only floating. floatingApplets=1 is
    // reasserted via plasmashellrc after layout apply and every theme switch.
    var bar = new Panel("org.kde.panel");
    bar.location = "top";
    bar.screen = screen;
    bar.lengthMode = "fill";
    bar.floating = false;
    bar.hiding = "none";
    bar.height = 32;

    // Panel Colorizer: transparent native background + per-applet glass.
    // Making the native background invisible isn't enough on its own — Plasma's
    // Adaptive opacity mode (the default when a fill panel has no explicit
    // panelOpacity override) renders opaque whenever a window touches the
    // screen edge under it, which is most of the time in real use. The
    // colorizer's own blurBehind + translucent fill keeps the top bar glass
    // regardless of what's open. Panel Colorizer requires the native panel
    // background to stay ENABLED at opacity 0 to publish its custom KWin blur
    // mask; disabling it makes floating-applet backgrounds render as flat
    // opaque pills. Both the continuous panel and per-applet paths carry the
    // same glass preset, while floatingApplets=1 selects the latter.
    // sourceType:0 forces the literal "custom" hex color instead of a
    // systemColor/Kirigami.Theme lookup (sourceType:1) — that lookup was
    // resolving to a near-white color regardless of the active color
    // scheme, which made the bar read as a faint, washed-out tint instead
    // of proper dark glass (mirrors the same bug found in the native
    // panel-background.svgz "ColorScheme-Background" recolor path).
    var colorizer = bar.addWidget("luisbocanegra.panel.colorizer");
    if (colorizer) {
        colorizer.currentConfigGroup = ["General"];
        colorizer.writeConfig("globalSettings", JSON.stringify({
            "nativePanel": {
                "background": { "enabled": true, "opacity": 0, "shadow": false },
                "floatingDialogs": true
            },
            "panel": {
                "normal": {
                    "enabled": true,
                    "blurBehind": true,
                    "backgroundColor": {
                        "enabled": true,
                        "alpha": 0.55,
                        "custom": "#1c1c1e",
                        "sourceType": 0
                    }
                }
            },
            "widgets": {
                "normal": {
                    "enabled": true,
                    "blurBehind": true,
                    "backgroundColor": {
                        "enabled": true,
                        "alpha": 0.55,
                        "custom": "#1c1c1e",
                        "sourceType": 0
                    }
                }
            }
        }));
        colorizer.currentConfigGroup = ["Configuration"];
        colorizer.writeConfig("hideWidget", "true");
    }

    bar.addWidget("org.kde.mac.tahoe.liquid.globalmenu");
    bar.addWidget("org.kde.plasma.panelspacer");

    // system tray — macOS style: only bluetooth, wifi, brightness visible
    var tray = bar.addWidget("org.kde.plasma.systemtray");
    tray.currentConfigGroup = ["General"];

    // shown = always visible, hidden = inside arrow, auto = KDE decides
    tray.writeConfig("shownItems", "org.kde.plasma.bluetooth,org.kde.plasma.networkmanagement,org.kde.plasma.brightness,org.kde.plasma.volume");
    tray.writeConfig("hiddenItems", "org.kde.plasma.clipboard,org.kde.plasma.devicenotifier,org.kde.plasma.manage-inputmethod,org.kde.plasma.mediacontroller,org.kde.plasma.notifications,org.kde.plasma.keyboardindicator,org.kde.plasma.weather,org.kde.kscreen,org.kde.plasma.keyboardlayout,org.kde.plasma.printmanager,org.kde.plasma.cameraindicator,org.kde.plasma.vault,org.kde.kdeconnect,org.kde.plasma.battery,Arch-Update,chrome_status_icon_1,discord,plasmashell_microphone,steam,spotify,telegram,slack");
    tray.writeConfig("iconSpacing", 3);

    bar.addWidget("org.kde.plasma.marginsseparator");

    var clock = bar.addWidget("org.kde.plasma.digitalclock");
    clock.currentConfigGroup = ["Appearance"];
    clock.writeConfig("autoFontAndSize", "false");
    clock.writeConfig("fontFamily", "SF Pro Text");
    clock.writeConfig("fontSize", 10);
    clock.writeConfig("fontWeight", 500);
    clock.writeConfig("showDate", "true");
    clock.writeConfig("use24hFormat", 1);
    clock.writeConfig("showSeconds", 0);
    clock.writeConfig("dateDisplayFormat", "BesideTime");
    clock.writeConfig("dateFormat", "custom");
    clock.writeConfig("customDateFormat", "ddd d ' | '");

    // ── bottom dock ─────────────────────────────────
    // floating, centered, large icons like macOS
    var dock = new Panel("org.kde.panel");
    dock.location = "bottom";
    dock.screen = screen;
    dock.alignment = "center";
    dock.lengthMode = "fit";
    dock.floating = true;
    dock.hiding = "dodgewindows";
    dock.height = 68;
    // opacity is set to translucent via plasmashellrc after layout apply
    // (JS scripting API does not expose panelOpacity)

    var launcher = dock.addWidget("org.kde.mac-tahoe-liquid-kde.launcher");
    launcher.currentConfigGroup = ["General"];
    launcher.writeConfig("icon", "view-app-grid");
    dock.addWidget("org.kde.plasma.marginsseparator");

    var tasks = dock.addWidget("org.kde.mac.tahoe.liquid.icontasks");
    tasks.currentConfigGroup = ["General"];
    // Filled by layout.py from the user's existing taskbar pins, applied to
    // every dock across every screen (see _append_launcher_restore).
    tasks.writeConfig("launchers", "");

    dock.addWidget("org.kde.plasma.marginsseparator");
    dock.addWidget("org.kde.mac-tahoe-liquid-kde.trashcan");
}
