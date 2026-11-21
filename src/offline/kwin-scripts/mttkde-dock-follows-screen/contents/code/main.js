// SPDX-License-Identifier: GPL-3.0-or-later
// macOS keeps one Dock and moves it to a display when the pointer is pushed
// against that display's bottom edge. Every screen has its own Dock here:
// the last one activated is shown (see the mttkde_dock_flush effect).
"use strict";

const EDGE = 2;          // px from the bottom edge that reveal the Dock
let current = null;      // geometry key of the screen holding the Dock

function key(g) { return g.x + "," + g.y + "," + g.width + "," + g.height; }

// Every Dock stays in "windows go below" mode so the desktop's free area,
// and the desktop icons, never change; the mttkde_dock_flush effect shows
// only the active Dock.
function moveDockTo(g) {
    const script =
        "panels().forEach(function(p){" +
        "  if (p.location!=='bottom' || p.widgets('org.kde.mac.tahoe.liquid.icontasks').length===0) return;" +
        "  p.hiding='windowsgobelow';" +
        "});";
    callDBus("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript", script);
}

function update() {
    const pos = workspace.cursorPos;
    const output = workspace.screenAt(pos);
    if (!output) return;
    const g = output.geometry;
    const k = key(g);
    if (current === null) { current = k; moveDockTo(g); return; }
    if (k === current) return;
    const dock = dockOn(output);
    const inDock = dock && pos.x >= dock.frameGeometry.x && pos.x < dock.frameGeometry.x + dock.frameGeometry.width
        && pos.y >= dock.frameGeometry.y;
    if (pos.y >= g.y + g.height - EDGE || inDock) { current = k; moveDockTo(g); }
}

// As on macOS, a window maximized while the Dock is shown on its screen
// stops above the Dock; windows maximized before the Dock moved there keep
// their size.
function dockOn(output) {
    for (const w of workspace.stackingOrder) {
        if (w.dock && w.output === output && w.frameGeometry.y > output.geometry.y + output.geometry.height / 2)
            return w;
    }
    return null;
}

function fitAboveDock(w) {
    if (!w.normalWindow || w.fullScreen || !w.output) return;
    if (key(w.output.geometry) !== current) return;
    const area = workspace.clientArea(KWin.MaximizeArea, w);
    const f = w.frameGeometry;
    // 3 = KWin::MaximizeFull; fall back to the geometry if the mode is hidden.
    const maximized = w.maximizeMode === 3 || (Math.abs(f.x - area.x) <= 1 && Math.abs(f.y - area.y) <= 1
        && Math.abs(f.width - area.width) <= 1 && Math.abs(f.height - area.height) <= 1);
    if (!maximized) return;
    const dock = dockOn(w.output);
    if (!dock) return;
    // Top of the Dock frame once the dock-flush effect has lowered it onto
    // the screen edge: 9 px inside its window, plus its 10 px floating gap.
    const top = dock.frameGeometry.y + 9 + 10;
    if (f.y + f.height <= top) return;
    w.frameGeometry = { x: area.x, y: area.y, width: area.width, height: top - area.y };
}

function watch(w) {
    if (!w.normalWindow) return;
    w.maximizedChanged.connect(function () { fitAboveDock(w); });
}

workspace.windowAdded.connect(function (w) { watch(w); fitAboveDock(w); });
workspace.windowList().forEach(watch);
workspace.cursorPosChanged.connect(update);
workspace.screensChanged.connect(function () { current = null; update(); });
update();
