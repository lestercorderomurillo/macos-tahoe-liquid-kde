// Add the base applications once per Dock, preserving user pins and order.
(function () {
    var dockApplications = [
        ["org.kde.dolphin.desktop"],
        ["firefox.desktop", "firefox-esr.desktop", "org.mozilla.firefox.desktop", "firefox_firefox.desktop"],
        ["thunderbird.desktop", "org.mozilla.Thunderbird.desktop", "thunderbird_thunderbird.desktop"],
        ["org.kde.merkuro.calendar.desktop"],
        ["org.kde.marknote.desktop"],
        ["org.kde.gwenview.desktop"],
        ["org.kde.elisa.desktop"],
        ["org.kde.haruna.desktop"],
        ["org.kde.discover.desktop"],
        ["systemsettings.desktop"]
    ];

    var ps = panels();
    for (var p = 0; p < ps.length; p++) {
        var ids = ps[p].widgetIds;
        for (var w = 0; w < ids.length; w++) {
            var tasks = ps[p].widgetById(ids[w]);
            if (!tasks || tasks.type !== "org.kde.mac.tahoe.liquid.icontasks") continue;
            tasks.currentConfigGroup = ["General"];
            if (Number(tasks.readConfig("dockPresetRevision", 0)) >= 1) continue;
            var pins = tasks.readConfig("launchers", []);
            if (typeof pins === "string") pins = pins ? pins.split(",") : [];
            for (var app = 0; app < dockApplications.length; app++) {
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
                if (present) continue;
                for (var i = 0; i < candidates.length; i++) {
                    if (applicationExists(candidates[i])) {
                        pins.push("applications:" + candidates[i]);
                        break;
                    }
                }
            }
            tasks.writeConfig("launchers", pins);
            tasks.writeConfig("dockPresetRevision", 1);
        }
    }
})();
