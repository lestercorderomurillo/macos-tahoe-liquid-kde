// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

var candidates = {
    "files": [
        "org.kde.dolphin.desktop",
        "org.gnome.Nautilus.desktop",
        "thunar.desktop",
        "pcmanfm-qt.desktop"
    ],
    "browser": [
        "firefox.desktop",
        "firefox-esr.desktop",
        "org.mozilla.firefox.desktop",
        "firefox_firefox.desktop",
        "chromium.desktop",
        "chromium-browser.desktop",
        "google-chrome.desktop",
        "com.google.Chrome.desktop",
        "brave-browser.desktop",
        "com.brave.Browser.desktop",
        "org.kde.falkon.desktop"
    ],
    "mail": [
        "thunderbird.desktop",
        "org.mozilla.Thunderbird.desktop",
        "thunderbird_thunderbird.desktop",
        "org.kde.kmail2.desktop",
        "org.gnome.Evolution.desktop",
        "org.gnome.Geary.desktop"
    ],
    "calendar": [
        "org.kde.merkuro.calendar.desktop",
        "org.kde.korganizer.desktop",
        "org.gnome.Calendar.desktop"
    ],
    "notes": [
        "org.kde.marknote.desktop",
        "org.kde.knotes.desktop",
        "org.gnome.Gnote.desktop",
        "org.gnome.Notes.desktop",
        "com.vixalien.sticky.desktop"
    ],
    "photos": [
        "org.kde.gwenview.desktop",
        "org.gnome.Loupe.desktop",
        "org.gnome.eog.desktop",
        "org.xfce.ristretto.desktop",
        "ristretto.desktop",
        "nomacs.desktop"
    ],
    "music": [
        "org.kde.elisa.desktop",
        "org.gnome.Rhythmbox3.desktop",
        "org.gnome.Music.desktop",
        "io.bassi.Amberol.desktop",
        "org.strawberrymusic.strawberry.desktop",
        "strawberry.desktop",
        "clementine.desktop",
        "audacious.desktop"
    ],
    "video": [
        "org.kde.haruna.desktop",
        "org.gnome.Showtime.desktop",
        "vlc.desktop",
        "org.videolan.VLC.desktop",
        "org.gnome.Totem.desktop",
        "io.github.celluloid_player.Celluloid.desktop",
        "mpv.desktop",
        "smplayer.desktop"
    ],
    "store": [
        "org.kde.discover.desktop",
        "org.gnome.Software.desktop"
    ],
    "settings": [
        "systemsettings.desktop"
    ]
};

function roleFor(launcherUrl, appId) {
    var url = String(launcherUrl || "").split("?")[0].split("#")[0];
    var preferred = {"preferred://filemanager": "files", "preferred://browser": "browser",
                     "preferred://mailer": "mail"};
    if (preferred[url]) return preferred[url];
    var desktopId = url.startsWith("applications:") ? url.substring(13) : url.substring(url.lastIndexOf("/") + 1);
    try { desktopId = decodeURIComponent(desktopId); } catch (e) { return ""; }
    var id = String(appId || "");
    if (id && !id.endsWith(".desktop")) id += ".desktop";
    for (var role in candidates) {
        if (candidates[role].indexOf(desktopId) !== -1 || candidates[role].indexOf(id) !== -1) return role;
    }
    return "";
}

// Material colors may invert luminance independently of the desktop mode.
function darkMode(themeName, backgroundLightness) {
    if (themeName === "MacTahoeLiquidKde-Dark") return true;
    if (themeName === "MacTahoeLiquidKde-Light") return false;
    return backgroundLightness < 0.5;
}

// Browsers retain their own identity and artwork, including Firefox.
function appearanceRoleFor(launcherUrl, appId) {
    var role = roleFor(launcherUrl, appId);
    return role === "browser" ? "" : role;
}
