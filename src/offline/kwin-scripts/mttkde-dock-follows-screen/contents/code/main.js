// SPDX-License-Identifier: GPL-3.0-or-later
// Move the actual Plasma panel so its input region, visibility and reserved
// space travel with its widgets and pins.
"use strict";

let edgeOutput = null;
function followBottomEdge() {
    if (!workspace.screens.length) return;
    const pos = workspace.cursorPos;
    const single = workspace.screens.length === 1;
    const output = single ? workspace.screens[0] : workspace.screenAt(pos);
    if (!output || (!single && pos.y < output.geometry.y + output.geometry.height - 1)) {
        edgeOutput = null;
        return;
    }
    if (edgeOutput === output.name) return;
    edgeOutput = output.name;
    const script = "(function () {" +
        "const target = screenForConnector(" + JSON.stringify(output.name) + ");" +
        "if (target < 0) return;" +
        "const docks = panels().filter(p => p.location === 'bottom' && " +
        "p.widgets().some(w => w.type === 'org.kde.mac.tahoe.liquid.icontasks'));" +
        "if (docks.length === 1 && docks[0].screen !== target) docks[0].screen = target;" +
        "})()";
    callDBus("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript", script);
}
workspace.cursorPosChanged.connect(followBottomEdge);
workspace.screensChanged.connect(function () { edgeOutput = null; followBottomEdge(); });
followBottomEdge();
