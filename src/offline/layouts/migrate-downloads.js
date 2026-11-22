// SPDX-License-Identifier: GPL-3.0-only
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
