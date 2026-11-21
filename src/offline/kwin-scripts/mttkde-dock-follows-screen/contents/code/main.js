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

workspace.cursorPosChanged.connect(update);
workspace.screensChanged.connect(function () { current = null; update(); });
update();
