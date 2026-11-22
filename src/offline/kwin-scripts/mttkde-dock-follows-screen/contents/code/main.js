// SPDX-License-Identifier: GPL-3.0-or-later
// Move the actual Plasma panel so its input region, visibility and reserved
// space travel with its widgets and pins.
"use strict";

// The pointer must rest on another screen's bottom edge this long before the
// Dock moves there, so a click near the bottom of a window, such as a chat
// input, does not pull the Dock over it.
const DWELL_MS = 2000;
// The mttkde_dock_flush effect slides the Dock down off its screen once the
// rest is over; move the panel only after that slide, so the Dock then rises
// from below the new screen's edge.
const SLIDE_MS = 220;
// px from the bottom edge that count as the edge (the same in the effect).
const EDGE = 2;

let edgeOutput = null;
let pendingOutput = null;
const dwell = new QTimer();
dwell.singleShot = true;
dwell.interval = DWELL_MS + SLIDE_MS;

function bottomEdgeOutput() {
    if (!workspace.screens.length) return null;
    const pos = workspace.cursorPos;
    const single = workspace.screens.length === 1;
    const output = single ? workspace.screens[0] : workspace.screenAt(pos);
    if (!output || (!single && pos.y < output.geometry.y + output.geometry.height - EDGE)) return null;
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

// With the always-visible Dock, as on macOS, a window maximized on the Dock's
// screen stops at the Dock's top edge; windows maximized before the Dock
// moved there keep their size. The installer turns this on (FitAboveDock)
// with the mttkde_dock_flush effect, which lowers the Dock onto the screen
// edge next to those windows.
const fitAboveDockEnabled = readConfig("FitAboveDock", false);
const FLUSH_GAP = 10;   // the floating gap the dock-flush effect removes

function dockOn(output) {
    for (const w of workspace.stackingOrder) {
        if (w.dock && !w.hidden && w.output === output
                && w.frameGeometry.y > output.geometry.y + output.geometry.height / 2)
            return w;
    }
    return null;
}

function fitAboveDock(w) {
    if (!fitAboveDockEnabled || !w.normalWindow || w.fullScreen || !w.output) return;
    // 3 = KWin::MaximizeFull.
    if (w.maximizeMode !== 3) return;
    const dock = dockOn(w.output);
    if (!dock) return;
    const area = workspace.clientArea(KWin.MaximizeArea, w);
    // The Dock's panel window is taller than its visible frame: Plasma's
    // floating panel keeps a 9 px shadow margin above the frame, and the
    // effect lowers the frame by its floating gap.
    const top = dock.frameGeometry.y + 9 + FLUSH_GAP;
    const f = w.frameGeometry;
    if (f.y + f.height <= top) return;
    w.frameGeometry = { x: area.x, y: area.y, width: area.width, height: top - area.y };
}

function watchWindow(w) {
    if (!w.normalWindow) return;
    w.maximizedChanged.connect(function () { fitAboveDock(w); });
}

workspace.windowAdded.connect(function (w) { watchWindow(w); fitAboveDock(w); });
workspace.windowList().forEach(watchWindow);
workspace.cursorPosChanged.connect(followBottomEdge);
workspace.screensChanged.connect(function () {
    edgeOutput = null;
    pendingOutput = null;
    dwell.stop();
    followBottomEdge();
});
followBottomEdge();
