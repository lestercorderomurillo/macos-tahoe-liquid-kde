// SPDX-License-Identifier: GPL-3.0-or-later
// macOS keeps one Dock and moves it to a display when the pointer is pushed
// against that display's bottom edge. Every screen has its own Dock here:
// the last one revealed stays shown, the others auto-hide. The shown Dock
// uses "windows go below", so it never resizes windows when it moves; it
// keeps floating with its rounded corners, and full-screen windows cover it.
"use strict";

const EDGE = 2;          // px from the bottom edge that reveal the Dock
let current = null;      // geometry key of the screen holding the Dock

function key(g) { return g.x + "," + g.y + "," + g.width + "," + g.height; }

function moveDockTo(g) {
    const script =
        "var x=" + (g.x + g.width / 2) + ",y=" + (g.y + g.height / 2) + ";" +
        "panels().forEach(function(p){" +
        "  if (p.location!=='bottom' || p.widgets('org.kde.mac.tahoe.liquid.icontasks').length===0) return;" +
        "  var s=screenGeometry(p.screen);" +
        "  var here=x>=s.x&&x<s.x+s.width&&y>=s.y&&y<s.y+s.height;" +
        "  p.hiding=here?'windowsgobelow':'autohide';" +
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
    if (pos.y >= g.y + g.height - EDGE) { current = k; moveDockTo(g); }
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
    const top = dock.frameGeometry.y;
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
