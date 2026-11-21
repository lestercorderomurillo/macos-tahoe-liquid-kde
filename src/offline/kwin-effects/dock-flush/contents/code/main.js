// SPDX-License-Identifier: GPL-3.0-or-later
// Plasma's non-floating panel drops the Dock's bottom border (square corners).
// Instead the Dock stays floating, and while a maximized window shares its
// screen it is lowered by its floating gap onto the screen edge, so the
// window above and the Dock below touch with no gap, as on macOS.
"use strict";

const GAP = 23;              // px between the floating Dock frame and the screen edge
const shifted = new Map();   // dock window -> animation id

function isDock(w) {
    return w && w.dock && w.y > w.screen.geometry.y + w.screen.geometry.height / 2;
}

// Maximized, or fitted above the Dock by the dock-follows-screen script.
function fillsScreen(w) {
    if (!w.normalWindow || w.minimized || w.fullScreen || w.deleted) return false;
    // Effects get no work area: a maximized window spans the screen width,
    // starts under the menu bar and reaches down to the Dock.
    const s = w.screen.geometry;
    return Math.abs(w.x - s.x) <= 1 && Math.abs(w.width - s.width) <= 1
        && w.y - s.y <= 48 && w.y + w.height >= s.y + s.height - 120;
}

// Output wrappers differ between accesses: compare screens by geometry.
function screenKey(w) {
    const g = w.screen.geometry;
    return g.x + "," + g.y + "," + g.width + "," + g.height;
}

function refresh() {
    const busy = new Set();
    for (const w of effects.stackingOrder) {
        if (fillsScreen(w) && w.isOnCurrentDesktop) busy.add(screenKey(w));
    }
    for (const d of effects.stackingOrder) {
        if (!isDock(d)) continue;
        const want = busy.has(screenKey(d));
        if (want && !shifted.has(d)) {
            d.setData(Effect.WindowForceBlurRole, true);
            shifted.set(d, set({
                window: d, duration: 160, curve: QEasingCurve.OutCubic,
                animations: [{ type: Effect.Translation, from: { value1: 0, value2: 0 }, to: { value1: 0, value2: GAP } }]
            }));
        } else if (!want && shifted.has(d)) {
            cancel(shifted.get(d));
            shifted.delete(d);
            animate({
                window: d, duration: 160, curve: QEasingCurve.OutCubic,
                animations: [{ type: Effect.Translation, from: { value1: 0, value2: GAP }, to: { value1: 0, value2: 0 } }]
            });
        }
    }
}

function watch(w) {
    if (!w || w.mttkdeFlushWatched) return;
    w.mttkdeFlushWatched = true;
    if (w.windowFrameGeometryChanged) w.windowFrameGeometryChanged.connect(refresh);
    if (w.windowMaximizedStateChanged) w.windowMaximizedStateChanged.connect(refresh);
    if (w.minimizedChanged) w.minimizedChanged.connect(refresh);
}

effects.windowAdded.connect(function (w) { watch(w); refresh(); });
effects.windowClosed.connect(function (w) { shifted.delete(w); refresh(); });
effects.desktopChanged && effects.desktopChanged.connect(refresh);
effects.stackingOrder.forEach(watch);
refresh();
