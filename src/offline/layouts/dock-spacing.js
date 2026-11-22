// SPDX-License-Identifier: GPL-3.0-only
// Preserve pins, widget settings and user separators outside these boundaries.
for (var panel of panels()) {
    var widgets = panel.widgets().sort((a, b) => a.index - b.index);
    for (var i = 1; i + 1 < widgets.length; ++i) {
        if (widgets[i].type !== "org.kde.plasma.marginsseparator") continue;
        var before = widgets[i - 1].type;
        var after = widgets[i + 1].type;
        if ((before === "org.kde.mac-tahoe-liquid-kde.launcher"
                && after === "org.kde.mac.tahoe.liquid.icontasks")
            || (before === "org.kde.mac.tahoe.liquid.icontasks"
                && (after === "org.kde.mac-tahoe-liquid-kde.trashcan"
                    || after === "org.kde.mac-tahoe-liquid-kde.downloads"))) {
            widgets[i].remove();
        }
    }
}

// Upgrade the Downloads shortcut installed by the previous Dock layout.
for (var panel of panels()) {
    var row = panel.widgets().sort((a, b) => a.index - b.index);
    for (var i = 1; i + 1 < row.length; ++i) {
        var folder = row[i];
        if (folder.type !== "org.kde.plasma.folder"
            || row[i - 1].type !== "org.kde.mac-tahoe-liquid-kde.dockseparator"
            || row[i + 1].type !== "org.kde.mac-tahoe-liquid-kde.trashcan") continue;
        folder.currentConfigGroup = ["General"];
        var url = "file://" + userDataPath("downloads").split("/").map(encodeURIComponent).join("/");
        if (folder.readConfig("url") !== url || folder.readConfig("icon") !== "folder-download") continue;
        var fan = panel.addWidget("org.kde.mac-tahoe-liquid-kde.downloads");
        if (fan) {
            fan.index = folder.index;
            folder.remove();
        }
    }
}
