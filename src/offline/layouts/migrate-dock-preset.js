// Add the base applications once per Dock, preserving user pins and order.
(function () {
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

    var ps = panels();
    for (var p = 0; p < ps.length; p++) {
        var ids = ps[p].widgetIds;
        for (var w = 0; w < ids.length; w++) {
            var tasks = ps[p].widgetById(ids[w]);
            if (!tasks || tasks.type !== "org.kde.mac.tahoe.liquid.icontasks") continue;
            tasks.currentConfigGroup = ["General"];
            var revision = Number(tasks.readConfig("dockPresetRevision", 0));
            var resolved = tasks.readConfig("dockPresetCategories", []);
            if (typeof resolved === "string") resolved = resolved ? resolved.split(",") : [];
            // Revision 1 already offered these candidates. Preserve deliberate
            // removals; newly supported equivalents can still fill empty roles.
            var legacyCounts = [1, 4, 3, 1, 1, 1, 1, 1, 1, 1];
            var pins = tasks.readConfig("launchers", []);
            if (typeof pins === "string") pins = pins ? pins.split(",") : [];
            for (var app = 0; app < dockApplications.length; app++) {
                var category = dockCategories[app];
                var requested = typeof mttkdeRequestedDockApps !== "undefined"
                    && mttkdeRequestedDockApps.indexOf(category) !== -1;
                if (resolved.indexOf(category) !== -1 && !requested) continue;
                var candidates = dockApplications[app];
                var present = false;
                for (var i = 0; i < candidates.length; i++) {
                    for (var j = 0; j < pins.length; j++) {
                        if (pins[j] === "applications:" + candidates[i]
                            || pins[j].endsWith("/" + candidates[i])) present = true;
                    }
                }
                if (app === 0 && pins.indexOf("preferred://filemanager") !== -1) present = true;
                if (app === 1 && pins.indexOf("preferred://browser") !== -1) present = true;
                if (app === 2 && pins.indexOf("preferred://mailer") !== -1) present = true;
                if (revision === 1 && !present && !requested) {
                    for (var i = 0; i < legacyCounts[app]; i++) {
                        if (applicationExists(candidates[i])) present = true;
                    }
                }
                if (present) {
                    if (resolved.indexOf(category) === -1) resolved.push(category);
                    continue;
                }
                for (var i = 0; i < candidates.length; i++) {
                    if (applicationExists(candidates[i])) {
                        var launcher = "applications:" + candidates[i];
                        if (pins.indexOf(launcher) === -1) pins.push(launcher);
                        if (resolved.indexOf(category) === -1) resolved.push(category);
                        break;
                    }
                }
            }
            tasks.writeConfig("launchers", pins);
            tasks.writeConfig("dockPresetCategories", resolved);
            tasks.writeConfig("dockPresetRevision", 2);
        }
    }
})();
