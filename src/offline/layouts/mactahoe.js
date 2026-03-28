// MacTahoe Liquid KDE — macOS Tahoe-style layout
// Top menu bar + bottom centered dock

// ── remove existing panels ──────────────────────
var old = panels();
for (var i = 0; i < old.length; i++) {
    old[i].remove();
}

// ── top menu bar (full width) ───────────────────
var bar = new Panel("org.kde.panel");
bar.location = "top";
bar.lengthMode = "fill";

bar.addWidget("org.kde.plasma.kickoff");
bar.addWidget("org.kde.plasma.appmenu");
bar.addWidget("org.kde.plasma.panelspacer");
bar.addWidget("org.kde.plasma.systemtray");
bar.addWidget("org.kde.plasma.digitalclock");

// ── bottom dock (centered, fit content) ─────────
var dock = new Panel("org.kde.panel");
dock.location = "bottom";
dock.alignment = "center";
dock.lengthMode = "fit";
dock.floating = true;

dock.addWidget("org.kde.plasma.icontasks");
dock.addWidget("org.kde.plasma.marginsseparator");
dock.addWidget("org.kde.mactahoe-liquid-kde.trash");
