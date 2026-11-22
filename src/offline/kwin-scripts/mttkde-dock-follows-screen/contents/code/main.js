// SPDX-License-Identifier: GPL-3.0-or-later
// Move the actual Plasma panel so its input region, visibility and reserved
// space travel with its widgets and pins.
"use strict";

// The pointer must rest on another screen's bottom edge this long before the
// Dock moves there, so a click near the bottom of a window, such as a chat
// input, does not pull the Dock over it.
const DWELL_MS = 2000;

let edgeOutput = null;
let pendingOutput = null;
const dwell = new QTimer();
dwell.singleShot = true;
dwell.interval = DWELL_MS;

function bottomEdgeOutput() {
    if (!workspace.screens.length) return null;
    const pos = workspace.cursorPos;
    const single = workspace.screens.length === 1;
    const output = single ? workspace.screens[0] : workspace.screenAt(pos);
    if (!output || (!single && pos.y < output.geometry.y + output.geometry.height - 1)) return null;
    return output;
}

function moveDockTo(name) {
    const script = "(function () {" +
        "const target = screenForConnector(" + JSON.stringify(name) + ");" +
        "if (target < 0) return;" +
        "const docks = panels().filter(p => p.location === 'bottom' && " +
        "p.widgets().some(w => w.type === 'org.kde.mac.tahoe.liquid.icontasks'));" +
        "if (docks.length === 1 && docks[0].screen !== target) docks[0].screen = target;" +
        "})()";
    callDBus("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript", script);
}

dwell.timeout.connect(function () {
    const output = bottomEdgeOutput();
    if (!output || output.name !== pendingOutput) return;
    edgeOutput = pendingOutput;
    pendingOutput = null;
    moveDockTo(edgeOutput);
});

function followBottomEdge() {
    const output = bottomEdgeOutput();
    if (!output) {
        edgeOutput = null;
        pendingOutput = null;
        dwell.stop();
        return;
    }
    if (edgeOutput === output.name || pendingOutput === output.name) return;
    // A single screen has nowhere else to move the Dock.
    if (workspace.screens.length === 1) {
        edgeOutput = output.name;
        moveDockTo(edgeOutput);
        return;
    }
    pendingOutput = output.name;
    dwell.start();
}

workspace.cursorPosChanged.connect(followBottomEdge);
workspace.screensChanged.connect(function () {
    edgeOutput = null;
    pendingOutput = null;
    dwell.stop();
    followBottomEdge();
});
followBottomEdge();
