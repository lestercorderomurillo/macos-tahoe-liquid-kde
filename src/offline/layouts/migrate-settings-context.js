// Suppress the vendor configuration shortcut on older Liquid KDE bars.
// Preserve explicitly saved preferences and independent panels.
for (var panel of panels()) {
    var widgets = panel.widgets();
    if (!widgets.some(w => w.type === "org.kde.mac.tahoe.liquid.globalmenu")) continue;
    for (var widget of widgets.filter(w => w.type === "luisbocanegra.panel.colorizer")) {
        // Older layouts stored the hide flag outside the applet's General group.
        widget.currentConfigGroup = ["Configuration"];
        var legacyHide = widget.readConfig("hideWidget", "unset");
        widget.currentConfigGroup = ["General"];
        if (String(legacyHide) === "true" && widget.readConfig("hideWidget", "unset") === "unset") {
            widget.writeConfig("hideWidget", true);
            widget.reloadConfig();
        }
        if (widget.readConfig("configureFromAllWidgets", "unset") === "unset") {
            widget.writeConfig("configureFromAllWidgets", false);
            widget.reloadConfig();
        }
    }
}
