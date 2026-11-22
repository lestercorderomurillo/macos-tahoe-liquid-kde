// SPDX-License-Identifier: GPL-3.0-or-later
// macOS keeps the Dock floating, with its rounded corners, even next to a
// maximized window. Plasma's always-visible panel de-floats as soon as a
// window touches it, and the non-floating panel drops its bottom border,
// which squares the Dock's corners. The installer keeps the always-visible
// Dock in "windows go below" mode, which never de-floats, and this effect
// lowers the Dock by its floating gap onto the screen edge while a maximized
// window shares its screen. The mttkde-dock-follows-screen script makes those
// windows stop at the lowered Dock's top edge.
"use strict";

const GAP = 10;              // px between the floating Dock frame and the screen edge
const shifted = new Map();   // dock window -> translation animation id

function screenKey(w) {
    const g = w.screen.geometry;
    return g.x + "," + g.y + "," + g.width + "," + g.height;
}

function isDock(w) {
    return w && w.dock && !w.deleted && w.y > w.screen.geometry.y + w.screen.geometry.height / 2;
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

function stop(d) {
    if (shifted.has(d)) { cancel(shifted.get(d)); shifted.delete(d); }
}

function refresh() {
    const busy = new Set();
    for (const w of effects.stackingOrder)
        if (fillsScreen(w) && w.onCurrentDesktop !== false) busy.add(screenKey(w));
    for (const d of effects.stackingOrder.filter(isDock)) {
        const lower = d.visible && busy.has(screenKey(d));
        if (lower && !shifted.has(d)) {
            d.setData(Effect.WindowForceBlurRole, true);
            // keepAlive false: a closed Dock must never stay painted as a ghost,
            // and the effect can then be unloaded safely.
            shifted.set(d, set({
                window: d, duration: 160, curve: QEasingCurve.OutCubic, keepAlive: false,
                animations: [{ type: Effect.Translation, from: { value1: 0, value2: 0 }, to: { value1: 0, value2: GAP } }]
            }));
        } else if (!lower && shifted.has(d)) {
            stop(d);
            animate({ window: d, duration: 160, curve: QEasingCurve.OutCubic, keepAlive: false,
                      animations: [{ type: Effect.Translation, from: { value1: 0, value2: GAP }, to: { value1: 0, value2: 0 } }] });
        }
    }
}

function watch(w) {
    if (!w || w.mttkdeFlushWatched) return;
    w.mttkdeFlushWatched = true;
    if (w.windowFrameGeometryChanged) w.windowFrameGeometryChanged.connect(refresh);
    if (w.windowMaximizedStateChanged) w.windowMaximizedStateChanged.connect(refresh);
    if (w.minimizedChanged) w.minimizedChanged.connect(refresh);
    if (w.windowHiddenChanged) w.windowHiddenChanged.connect(refresh);
}

effects.windowAdded.connect(function (w) { watch(w); refresh(); });
effects.windowClosed.connect(function (w) { stop(w); refresh(); });
effects.desktopChanged.connect(refresh);
effects.stackingOrder.forEach(watch);
refresh();
