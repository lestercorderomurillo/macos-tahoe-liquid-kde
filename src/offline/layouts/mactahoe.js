// MacTahoe Liquid KDE — macOS Tahoe-style layout
// Top menu bar (flush) + bottom dock (floating, large icons)

// ── remove existing panels ──────────────────────
var old = panels();
for (var i = 0; i < old.length; i++) {
    old[i].remove();
}

// ── top menu bar ────────────────────────────────
// flush with screen edge (not floating), thin, full width
var bar = new Panel("org.kde.panel");
bar.location = "top";
bar.lengthMode = "fill";
bar.floating = false;
bar.height = 2 * Math.ceil(gridUnit * 1.4 / 2);

bar.addWidget("org.kde.plasma.kickoff");
bar.addWidget("org.kde.plasma.appmenu");
bar.addWidget("org.kde.plasma.panelspacer");
bar.addWidget("org.kde.plasma.systemtray");
bar.addWidget("org.kde.plasma.digitalclock");

// ── bottom dock ─────────────────────────────────
// floating, centered, large icons like macOS
var dock = new Panel("org.kde.panel");
dock.location = "bottom";
dock.alignment = "center";
dock.lengthMode = "fit";
dock.floating = true;
dock.height = 2 * Math.ceil(gridUnit * 3.5 / 2);

var launcher = dock.addWidget("org.kde.plasma.kickerdash");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "view-app-grid");
dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.plasma.icontasks");
dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.mactahoe-liquid-kde.trash");
