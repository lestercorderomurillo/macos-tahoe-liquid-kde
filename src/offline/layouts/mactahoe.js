// MacTahoe Liquid KDE — macOS Tahoe-style layout
// Top menu bar (flush) + bottom dock (floating, large icons)

// ── remove existing panels ──────────────────────
var old = panels();
for (var i = 0; i < old.length; i++) {
    old[i].remove();
}

// ── top menu bar ────────────────────────────────
// flush with screen edge (not floating), thin, full width
var bar = new Panel("org.kde.panel");
bar.location = "top";
bar.lengthMode = "fill";
bar.floating = false;
bar.height = 32;

// panel colorizer: transparent background
var colorizer = bar.addWidget("luisbocanegra.panel.colorizer");
colorizer.currentConfigGroup = ["General"];
colorizer.writeConfig("globalSettings", JSON.stringify({
    "nativePanel": {
        "background": { "enabled": false, "opacity": 0, "shadow": false },
        "floatingDialogs": false
    }
}));
colorizer.currentConfigGroup = ["Configuration"];
colorizer.writeConfig("hideWidget", "true");

bar.addWidget("org.kde.plasma.kickoff");
bar.addWidget("org.kde.plasma.appmenu");
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
clock.writeConfig("showDate", "false");
clock.writeConfig("use24hFormat", 2);
clock.writeConfig("showSeconds", 0);
clock.writeConfig("dateDisplayFormat", "BesideTime");
clock.writeConfig("dateFormat", "shortDate");
clock.writeConfig("enabledCalendarPlugins", "");

// ── bottom dock ─────────────────────────────────
// floating, centered, large icons like macOS
var dock = new Panel("org.kde.panel");
dock.location = "bottom";
dock.alignment = "center";
dock.lengthMode = "fit";
dock.floating = true;
dock.height = 2 * Math.ceil(gridUnit * 3.5 / 2);

var launcher = dock.addWidget("org.kde.plasma.kickerdash");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "view-app-grid");
dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.plasma.icontasks");
dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.mactahoe-liquid-kde.trash");
