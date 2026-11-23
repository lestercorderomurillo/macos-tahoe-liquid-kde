// Suppress the vendor configuration shortcut on older Liquid KDE bars.
// Preserve explicitly saved preferences and independent panels.
for (var panel of panels()) {
    var widgets = panel.widgets();
    if (!widgets.some(w => w.type === "org.kde.mac.tahoe.liquid.globalmenu")) continue;
    for (var widget of widgets.filter(w => w.type === "luisbocanegra.panel.colorizer")) {
        widget.currentConfigGroup = ["General"];
        if (widget.readConfig("configureFromAllWidgets", "unset") === "unset") {
            widget.writeConfig("configureFromAllWidgets", false);
            widget.reloadConfig();
        }
    }
}
