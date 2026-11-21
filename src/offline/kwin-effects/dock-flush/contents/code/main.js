// SPDX-License-Identifier: GPL-3.0-or-later
// macOS Dock on several displays, for Plasma's one-Dock-per-screen layout.
// - Every Dock stays in "windows go below" mode (set by the
//   mttkde-dock-follows-screen script), so the desktop's free area never
//   changes and desktop icons never rearrange.
// - Only the last activated Dock is shown; the others are faded out. Pushing
//   the pointer against a screen's bottom edge, or into its Dock, activates it.
// - Plasma's non-floating panel drops the Dock's bottom border (square
//   corners), so the shown Dock stays floating and, while a maximized window
//   shares its screen, is lowered by its floating gap onto the screen edge.
"use strict";

const GAP = 10;              // px between the floating Dock frame and the screen edge
const EDGE = 2;              // px from the bottom edge that reveal a Dock
const shifted = new Map();   // dock window -> translation animation id
const faded = new Map();     // dock window -> opacity animation id
let active = null;           // screen key of the shown Dock

function screenKeyOf(output) {
    const g = output.geometry;
    return g.x + "," + g.y + "," + g.width + "," + g.height;
}
function screenKey(w) { return screenKeyOf(w.screen); }

function isDock(w) {
    return w && w.dock && w.y > w.screen.geometry.y + w.screen.geometry.height / 2;
}

function docks() { return effects.stackingOrder.filter(isDock); }

// Maximized, or fitted above the Dock by the dock-follows-screen script.
function fillsScreen(w) {
    if (!w.normalWindow || w.minimized || w.fullScreen || w.deleted) return false;
    // Effects get no work area: a maximized window spans the screen width,
    // starts under the menu bar and reaches down to the Dock.
    const s = w.screen.geometry;
    return Math.abs(w.x - s.x) <= 1 && Math.abs(w.width - s.width) <= 1
        && w.y - s.y <= 48 && w.y + w.height >= s.y + s.height - 120;
}

function stop(map, d) {
    if (map.has(d)) { cancel(map.get(d)); map.delete(d); }
}

function refresh() {
    const busy = new Set();
    for (const w of effects.stackingOrder) {
        if (fillsScreen(w) && w.onCurrentDesktop !== false) busy.add(screenKey(w));
    }
    for (const d of docks()) {
        const shown = active === null || screenKey(d) === active;
        // Fade the inactive Docks out instead of auto-hiding them.
        if (!shown && !faded.has(d)) {
            faded.set(d, set({
                window: d, duration: 140, curve: QEasingCurve.InCubic, keepAlive: false,
                animations: [{ type: Effect.Opacity, from: 1, to: 0 }]
            }));
        } else if (shown && faded.has(d)) {
            stop(faded, d);
            animate({ window: d, duration: 160, curve: QEasingCurve.OutCubic, keepAlive: false,
                      animations: [{ type: Effect.Opacity, from: 0, to: 1 }] });
        }
        const lower = shown && d.visible && busy.has(screenKey(d));
        if (lower && !shifted.has(d)) {
            d.setData(Effect.WindowForceBlurRole, true);
            shifted.set(d, set({
                window: d, duration: 160, curve: QEasingCurve.OutCubic, keepAlive: false,
                animations: [{ type: Effect.Translation, from: { value1: 0, value2: 0 }, to: { value1: 0, value2: GAP } }]
            }));
        } else if (!lower && shifted.has(d)) {
            stop(shifted, d);
            animate({ window: d, duration: 160, curve: QEasingCurve.OutCubic, keepAlive: false,
                      animations: [{ type: Effect.Translation, from: { value1: 0, value2: GAP }, to: { value1: 0, value2: 0 } }] });
        }
    }
}

function pointerMoved(pos) {
    for (const d of docks()) {
        const s = d.screen.geometry;
        if (pos.x < s.x || pos.x >= s.x + s.width || pos.y < s.y || pos.y >= s.y + s.height) continue;
        const key = screenKeyOf(d.screen);
        if (key === active) return;
        const atEdge = pos.y >= s.y + s.height - EDGE;
        const inDock = pos.x >= d.x && pos.x < d.x + d.width && pos.y >= d.y;
        if (active === null || atEdge || inDock) { active = key; refresh(); }
        return;
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
// A closed Dock (Plasma restarting) must not stay painted as a ghost.
effects.windowClosed.connect(function (w) { stop(shifted, w); stop(faded, w); refresh(); });
effects.mouseChanged.connect(function (pos) { pointerMoved(pos); });
effects.stackingOrder.forEach(watch);
pointerMoved(effects.cursorPos);
refresh();
