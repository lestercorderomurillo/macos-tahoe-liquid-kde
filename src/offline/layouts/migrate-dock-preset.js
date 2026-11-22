// Apply the 0.64 defaults once per Dock, or on explicit reset, preserving pin order.
(function () {
    var dockApplications = [
        ["org.kde.dolphin.desktop", "org.gnome.Nautilus.desktop", "thunar.desktop", "pcmanfm-qt.desktop"],
        ["firefox.desktop", "firefox-esr.desktop", "org.mozilla.firefox.desktop", "firefox_firefox.desktop", "chromium.desktop", "chromium-browser.desktop", "google-chrome.desktop", "com.google.Chrome.desktop", "brave-browser.desktop", "com.brave.Browser.desktop", "org.kde.falkon.desktop"],
        ["thunderbird.desktop", "org.mozilla.Thunderbird.desktop", "thunderbird_thunderbird.desktop", "org.kde.kmail2.desktop", "org.gnome.Evolution.desktop", "org.gnome.Geary.desktop"],
        ["org.kde.gwenview.desktop", "org.gnome.Loupe.desktop", "org.gnome.eog.desktop", "org.xfce.ristretto.desktop", "ristretto.desktop", "nomacs.desktop"],
        ["org.kde.merkuro.calendar.desktop", "org.kde.korganizer.desktop", "org.gnome.Calendar.desktop"],
        ["org.kde.marknote.desktop", "org.kde.knotes.desktop", "org.gnome.Gnote.desktop", "org.gnome.Notes.desktop", "com.vixalien.sticky.desktop"],
        ["org.kde.haruna.desktop", "org.gnome.Showtime.desktop", "vlc.desktop", "org.videolan.VLC.desktop", "org.gnome.Totem.desktop", "io.github.celluloid_player.Celluloid.desktop", "mpv.desktop", "smplayer.desktop"],
        ["org.kde.elisa.desktop", "org.gnome.Rhythmbox3.desktop", "org.gnome.Music.desktop", "io.bassi.Amberol.desktop", "org.strawberrymusic.strawberry.desktop", "strawberry.desktop", "clementine.desktop", "audacious.desktop"],
        ["org.kde.discover.desktop", "org.gnome.Software.desktop"],
        ["systemsettings.desktop"]
    ];
    var dockCategories = ["files", "browser", "mail", "photos", "calendar", "notes", "video", "music", "store", "settings"];

    var ps = panels();
    for (var p = 0; p < ps.length; p++) {
        var ids = ps[p].widgetIds;
        for (var w = 0; w < ids.length; w++) {
            var tasks = ps[p].widgetById(ids[w]);
            if (!tasks || tasks.type !== "org.kde.mac.tahoe.liquid.icontasks") continue;
            tasks.currentConfigGroup = ["General"];
            var revision = Number(tasks.readConfig("dockPresetRevision", 0));
            var applyDefaults = revision < 3
                || (typeof mttkdeResetDock !== "undefined" && mttkdeResetDock);
            if (applyDefaults) {
                ps[p].location = "bottom";
                ps[p].alignment = "center";
                ps[p].lengthMode = "fit";
                ps[p].floating = true;
                ps[p].opacity = "translucent";
                if (typeof mttkdeDockVisibility !== "undefined") ps[p].hiding = mttkdeDockVisibility;
                ps[p].height = 68;
            }
            if (applyDefaults && (typeof mttkdeDockAppearance === "undefined" || mttkdeDockAppearance === "auto")) {
                tasks.writeConfig("macOSDockIcons", true);
            }
            if (typeof mttkdeDockAppearance !== "undefined" && mttkdeDockAppearance !== "keep" && mttkdeDockAppearance !== "auto") {
                tasks.writeConfig("macOSDockIcons", mttkdeDockAppearance === "macos");
            }
            var resolved = tasks.readConfig("dockPresetCategories", []);
            if (typeof resolved === "string") resolved = resolved ? resolved.split(",") : [];
            var pins = tasks.readConfig("launchers", []);
            if (typeof pins === "string") pins = pins ? pins.split(",") : [];
            for (var app = 0; app < dockApplications.length; app++) {
                var category = dockCategories[app];
                var requested = typeof mttkdeRequestedDockApps !== "undefined"
                    && mttkdeRequestedDockApps.indexOf(category) !== -1;
                if (!applyDefaults && !requested) continue;
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
                if (present) {
                    if (resolved.indexOf(category) === -1) resolved.push(category);
                    continue;
                }
                // Offered once already and no longer pinned: the user unpinned it.
                // Never pin it again, not even on a reset or an update.
                if (!requested && revision >= 3 && resolved.indexOf(category) !== -1) continue;
                for (var i = 0; i < candidates.length; i++) {
                    if (applicationExists(candidates[i])) {
                        var launcher = "applications:" + candidates[i];
                        if (pins.indexOf(launcher) === -1) pins.push(launcher);
                        if (resolved.indexOf(category) === -1) resolved.push(category);
                        break;
                    }
                }
            }
            var appsPin = "applications:org.kde.mac-tahoe-liquid-kde.apps.desktop";
            if (typeof userLauncherTypes === "undefined" && applicationExists("org.kde.mac-tahoe-liquid-kde.apps.desktop")
                    && ps[p].widgetIds.some(id => ps[p].widgetById(id).type === "org.kde.mac-tahoe-liquid-kde.launcher")) {
                // Convert only a recognizable factory sequence. A custom pin or a
                // manually reordered row keeps the user's relative application order.
                if (revision >= 1 && !tasks.readConfig("appsPinInitialized", false) && !pins.includes(appsPin)) {
                    var oldOrder = ["files", "browser", "mail", "calendar", "notes", "photos", "music", "video", "store", "settings"];
                    var preferred = {"preferred://filemanager": "files", "preferred://browser": "browser", "preferred://mailer": "mail"};
                    var categories = pins.map(url => preferred[url] || dockCategories[dockApplications.findIndex(
                        aliases => aliases.some(id => url === "applications:" + id || url.endsWith("/" + id)))]);
                    var originalOrder = categories.every((role, index) => role && (index === 0
                        || oldOrder.indexOf(categories[index - 1]) < oldOrder.indexOf(role)));
                    if (originalOrder) {
                        var ranks = new Map(pins.map((url, index) => [url, dockCategories.indexOf(categories[index])]));
                        pins.sort((left, right) => ranks.get(left) - ranks.get(right));
                    }
                }
                var filesIndex = pins.findIndex(url => url === "preferred://filemanager"
                    || dockApplications[0].some(id => url === "applications:" + id || url.endsWith("/" + id)));
                if (pins.indexOf(appsPin) === -1 && !tasks.readConfig("appsPinInitialized", false))
                    pins.splice(filesIndex + 1, 0, appsPin);
                tasks.writeConfig("appsPinInitialized", true);
            }
            tasks.writeConfig("launchers", pins);
            tasks.writeConfig("dockPresetCategories", resolved);
            tasks.writeConfig("dockPresetRevision", Math.max(revision, 3));
        }
    }
})();
