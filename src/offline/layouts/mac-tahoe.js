// MacTahoe Liquid KDE — macOS Tahoe-style layout
// Top menu bar (flush) + bottom dock (floating, large icons)
// Applied per-screen so multi-monitor setups get a matching bar + dock on
// every display, not just the primary one.

// ── remove existing panels ──────────────────────
var old = panels();
var launcherPresets = {};
var dockPresetRevisions = {};
var dockPresetCategories = {};
var dockIconChoices = {};
for (var p = 0; p < old.length; p++) {
    var widgets = old[p].widgetIds;
    for (var w = 0; w < widgets.length; w++) {
        var widget = old[p].widgetById(widgets[w]);
        if (widget && widget.type === "org.kde.mac.tahoe.liquid.icontasks") {
            widget.currentConfigGroup = ["General"];
            dockIconChoices[old[p].screen] = widget.readConfig("macOSDockIcons", false);
            dockPresetRevisions[old[p].screen] = Number(widget.readConfig("dockPresetRevision", 0));
            dockPresetCategories[old[p].screen] = widget.readConfig("dockPresetCategories", []);
        }
        if (widget && widget.type === "org.kde.mac-tahoe-liquid-kde.launcher") {
            widget.currentConfigGroup = ["General"];
            var preset = Number(widget.readConfig("launcherPreset", 0));
            if (preset === 1 || preset === 2) {
                launcherPresets[old[p].screen] = preset;
            }
        }
    }
}
for (var i = 0; i < old.length; i++) {
    old[i].remove();
}

for (var screen = 0; screen < screenCount; screen++) {
    // ── top menu bar ────────────────────────────────
    // Top bar, flush panel with applets-only floating. floatingApplets=1 is
    // reasserted via plasmashellrc after layout apply and every theme switch.
    if (typeof mttkdeTopPanel === "undefined" || mttkdeTopPanel) {
    var bar = new Panel("org.kde.panel");
    bar.location = "top";
    bar.screen = screen;
    bar.lengthMode = "fill";
    bar.floating = false;
    bar.hiding = "none";
    bar.height = 32;

    // Panel Colorizer hides the continuous native panel background. Do not add
    // panel/widgets color layers here: both render at once with applets-only
    // floating and produce a full-width gray strip plus dark blocks behind
    // individual applets. Plasma's own floating-applet surfaces provide the
    // intended light/dark-aware glass treatment.
    var colorizer = bar.addWidget("luisbocanegra.panel.colorizer");
    if (colorizer) {
        colorizer.currentConfigGroup = ["General"];
        colorizer.writeConfig("globalSettings", JSON.stringify({
            "nativePanel": {
                "background": { "enabled": false, "opacity": 0, "shadow": false },
                "floatingDialogs": true
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
    }
    if (typeof mttkdeDock === "undefined" || mttkdeDock) {
    var dock = new Panel("org.kde.panel");
    dock.location = "bottom";
    dock.screen = screen;
    dock.alignment = "center";
    dock.lengthMode = "fit";
    dock.floating = true;
    // Auto-hide avoids the stuck-visible dodge behavior reported in issue #87.
    dock.hiding = "autohide";
    dock.height = 68;
    // opacity is set to translucent via plasmashellrc after layout apply
    // (JS scripting API does not expose panelOpacity)

    var launcher = dock.addWidget("org.kde.mac-tahoe-liquid-kde.launcher");
    launcher.currentConfigGroup = ["General"];
    launcher.writeConfig("icon", "view-app-grid");
    // The installer selects the new edition when migrating between editions.
    if (typeof mttkdeLauncherPreset !== "undefined"
            && (mttkdeLauncherPreset === 1 || mttkdeLauncherPreset === 2)) {
        launcher.writeConfig("launcherPreset", mttkdeLauncherPreset);
    } else if (launcherPresets[dock.screen] !== undefined) {
        launcher.writeConfig("launcherPreset", launcherPresets[dock.screen]);
    }

    var tasks = dock.addWidget("org.kde.mac.tahoe.liquid.icontasks");
    tasks.currentConfigGroup = ["General"];
    // Base Dock: use the first installed desktop ID for each application.
    // Existing user pins are restored by layout.py after this layout is created.
    var dockApplications = [
        ["org.kde.dolphin.desktop", "org.gnome.Nautilus.desktop", "thunar.desktop", "pcmanfm-qt.desktop"],
        ["firefox.desktop", "firefox-esr.desktop", "org.mozilla.firefox.desktop", "firefox_firefox.desktop", "chromium.desktop", "chromium-browser.desktop", "google-chrome.desktop", "com.google.Chrome.desktop", "brave-browser.desktop", "com.brave.Browser.desktop", "org.kde.falkon.desktop"],
        ["thunderbird.desktop", "org.mozilla.Thunderbird.desktop", "thunderbird_thunderbird.desktop", "org.kde.kmail2.desktop", "org.gnome.Evolution.desktop", "org.gnome.Geary.desktop"],
        ["org.kde.merkuro.calendar.desktop", "org.kde.korganizer.desktop", "org.gnome.Calendar.desktop"],
        ["org.kde.marknote.desktop", "org.kde.knotes.desktop", "org.gnome.Gnote.desktop", "org.gnome.Notes.desktop", "com.vixalien.sticky.desktop"],
        ["org.kde.gwenview.desktop", "org.gnome.Loupe.desktop", "org.gnome.eog.desktop", "org.xfce.ristretto.desktop", "ristretto.desktop", "nomacs.desktop"],
        ["org.kde.elisa.desktop", "org.gnome.Rhythmbox3.desktop", "org.gnome.Music.desktop", "io.bassi.Amberol.desktop", "org.strawberrymusic.strawberry.desktop", "strawberry.desktop", "clementine.desktop", "audacious.desktop"],
        ["org.kde.haruna.desktop", "org.gnome.Showtime.desktop", "vlc.desktop", "org.videolan.VLC.desktop", "org.gnome.Totem.desktop", "io.github.celluloid_player.Celluloid.desktop", "mpv.desktop", "smplayer.desktop"],
        ["org.kde.discover.desktop", "org.gnome.Software.desktop"],
        ["systemsettings.desktop"]
    ];
    var dockCategories = ["files", "browser", "mail", "calendar", "notes", "photos", "music", "video", "store", "settings"];
    var dockLaunchers = [];
    var resolvedDockCategories = [];
    for (var app = 0; app < dockApplications.length; app++) {
        for (var candidate = 0; candidate < dockApplications[app].length; candidate++) {
            var desktopId = dockApplications[app][candidate];
            if (applicationExists(desktopId)) {
                dockLaunchers.push("applications:" + desktopId);
                resolvedDockCategories.push(dockCategories[app]);
                break;
            }
        }
    }
    tasks.writeConfig("launchers", dockLaunchers);
    tasks.writeConfig("macOSDockIcons", dockIconChoices[dock.screen] || false);
    tasks.writeConfig("dockPresetRevision", dockPresetRevisions[dock.screen] || 0);
    tasks.writeConfig("dockPresetCategories", dockPresetCategories[dock.screen] || []);

    dock.addWidget("org.kde.mac-tahoe-liquid-kde.trashcan");
}
}
