// MacTahoe Liquid KDE — reset to default KDE layout

var old = panels();
for (var i = 0; i < old.length; i++) {
    old[i].remove();
}

var panel = new Panel("org.kde.panel");
panel.location = "bottom";
panel.lengthMode = "fill";

panel.addWidget("org.kde.plasma.kickoff");
panel.addWidget("org.kde.plasma.pager");
panel.addWidget("org.kde.plasma.icontasks");
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", "true");
clock.writeConfig("use24hFormat", 0);
clock.writeConfig("dateDisplayFormat", "BesideTime");
panel.addWidget("org.kde.plasma.showdesktop");
