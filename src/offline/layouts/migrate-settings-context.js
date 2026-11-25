// Repair the live Liquid bars after Plasma has restored the final containments.
// A restored copy can have the exact same applets but none of the settings
// written by the layout. Keep the original panel, its pins and its applet IDs.
var originals = new Set();
for (var panel of panels().sort((a, b) => a.id - b.id)) {
    if (panel.screen < 0) continue;
    var items = panel.widgets();
    var types = items.map(w => w.type);
    var bar = panel.location === "top" && types.includes("org.kde.mac.tahoe.liquid.globalmenu");
    var dock = panel.location === "bottom" && types.includes("org.kde.mac-tahoe-liquid-kde.trashcan");
    var anchor = items.find(w => bar ? w.type === "luisbocanegra.panel.colorizer"
                                    : dock && w.type === "org.kde.mac.tahoe.liquid.icontasks");
    if (!anchor) continue;
    var signature = JSON.stringify([panel.screen, panel.location, types]);
    anchor.currentConfigGroup = ["General"];
    var keys = bar ? ["hideWidget", "configureFromAllWidgets"] : ["dockPresetRevision", "launchers"];
    if (originals.has(signature) && keys.every(k => anchor.readConfig(k, "unset") === "unset")) {
        panel.remove();
        continue;
    }
    originals.add(signature);
}
for (var panel of panels()) {
    if (panel.location !== "top") continue;
    var widgets = panel.widgets();
    if (!widgets.some(w => w.type === "org.kde.mac.tahoe.liquid.globalmenu")) continue;
    for (var widget of widgets.filter(w => w.type === "luisbocanegra.panel.colorizer")) {
        widget.currentConfigGroup = ["General"];
        if (widget.readConfig("hideWidget", "unset") === "unset") {
            widget.writeConfig("hideWidget", true);
        }
        var settings = JSON.parse(widget.readConfig("globalSettings", "{}"));
        var nativePanel = settings.nativePanel || {};
        var background = nativePanel.background || {};
        if (background.enabled !== false || background.opacity !== 0 || background.shadow !== false) {
            background.enabled = false;
            background.opacity = 0;
            background.shadow = false;
            nativePanel.background = background;
            nativePanel.floatingDialogs = true;
            settings.nativePanel = nativePanel;
            widget.writeConfig("globalSettings", JSON.stringify(settings));
        }
        if (widget.readConfig("configureFromAllWidgets", "unset") === "unset") {
            widget.writeConfig("configureFromAllWidgets", false);
        }
        widget.reloadConfig();
    }
}
