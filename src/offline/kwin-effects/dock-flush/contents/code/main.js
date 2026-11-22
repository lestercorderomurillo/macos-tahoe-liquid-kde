// SPDX-License-Identifier: GPL-3.0-or-later
// macOS Dock motion for Plasma's single movable Dock.
//
// Changing screen: once the pointer has rested DWELL_MS on another screen's
// bottom edge, the Dock slides down off its screen; the
// mttkde-dock-follows-screen script then moves it (after the slide), and the
// Dock slides up from below the new screen's edge into place.
//
// Flush next to maximized windows (FitAboveDock, the always-visible Dock):
// Plasma de-floats an always-visible panel touched by a window and squares
// the Dock's corners, so the installer keeps it in "windows go below" mode
// and this effect lowers it by its floating gap onto the screen edge while a
// maximized window shares its screen. The script makes those windows stop at
// the lowered Dock's top edge.
"use strict";

const GAP = 10;              // px between the floating Dock frame and the screen edge
const DWELL_MS = 2000;       // the script moves the Dock DWELL_MS + SLIDE_MS after
const SLIDE_MS = 220;
const EDGE = 2;              // px from the bottom edge that count as the edge
const flushEnabled = effect.readConfig("FitAboveDock", false);

const shifted = new Map();   // dock window -> flush translation id
let leaving = null;          // { dock, id } while the Dock slides down
let waitId = null;           // no-op animation timing the pointer's rest
let waitStart = 0;          // when that rest began (ms)
let pending = null;          // screen key the pointer rests on
let dockScreen = null;       // screen key the Dock was last on

function keyOf(output) {
    const g = output.geometry;
    return g.x + "," + g.y + "," + g.width + "," + g.height;
}

function isDock(w) {
    return w && w.dock && !w.deleted && w.y > w.screen.geometry.y + w.screen.geometry.height / 2;
}

function theDock() {
    const docks = effects.stackingOrder.filter(isDock);
    return docks.length === 1 ? docks[0] : null;
}

// Distance that takes the Dock frame fully below its screen's edge.
function below(d) {
    const s = d.screen.geometry;
    return s.y + s.height - d.y;
}

// Maximized, or fitted above the Dock by the dock-follows-screen script.
function fillsScreen(w) {
    if (!w.normalWindow || w.minimized || w.fullScreen || w.deleted) return false;
    const s = w.screen.geometry;
    return Math.abs(w.x - s.x) <= 1 && Math.abs(w.width - s.width) <= 1
        && w.y - s.y <= 48 && w.y + w.height >= s.y + s.height - 120;
}

function stopFlush(d) {
    if (shifted.has(d)) { cancel(shifted.get(d)); shifted.delete(d); }
}

function busyScreens() {
    const busy = new Set();
    for (const w of effects.stackingOrder)
        if (fillsScreen(w) && w.onCurrentDesktop !== false) busy.add(keyOf(w.screen));
    return busy;
}

function flushTo(d, from) {
    d.setData(Effect.WindowForceBlurRole, true);
    // keepAlive false: a closed Dock must never stay painted as a ghost, and
    // the effect can then be unloaded safely.
    shifted.set(d, set({
        window: d, duration: from === 0 ? 160 : 260, curve: QEasingCurve.OutCubic, keepAlive: false,
        animations: [{ type: Effect.Translation, from: { value1: 0, value2: from }, to: { value1: 0, value2: GAP } }]
    }));
}

function refresh() {
    if (!flushEnabled) return;
    const busy = busyScreens();
    for (const d of effects.stackingOrder.filter(isDock)) {
        if (leaving && leaving.dock === d) continue;
        const lower = d.visible && busy.has(keyOf(d.screen));
        if (lower && !shifted.has(d)) {
            flushTo(d, 0);
        } else if (!lower && shifted.has(d)) {
            stopFlush(d);
            animate({ window: d, duration: 160, curve: QEasingCurve.OutCubic, keepAlive: false,
                      animations: [{ type: Effect.Translation, from: { value1: 0, value2: GAP }, to: { value1: 0, value2: 0 } }] });
        }
    }
}

function slideOut(d) {
    if (leaving || !d.visible) return;
    const from = shifted.has(d) ? GAP : 0;
    stopFlush(d);
    leaving = { dock: d, id: set({
        window: d, duration: SLIDE_MS, curve: QEasingCurve.InCubic, keepAlive: false,
        animations: [{ type: Effect.Translation, from: { value1: 0, value2: from }, to: { value1: 0, value2: below(d) } }]
    }) };
}

function slideIn(d) {
    if (leaving && leaving.dock === d) { cancel(leaving.id); leaving = null; }
    if (!d.visible) { refresh(); return; }
    // One movement: up from below the edge straight to the Dock's place,
    // flush with the edge when a maximized window shares the screen.
    if (flushEnabled && busyScreens().has(keyOf(d.screen))) {
        stopFlush(d);
        flushTo(d, below(d));
    } else {
        animate({ window: d, duration: 260, curve: QEasingCurve.OutCubic, keepAlive: false,
                  animations: [{ type: Effect.Translation, from: { value1: 0, value2: below(d) }, to: { value1: 0, value2: 0 } }] });
    }
    refresh();
}

// Scripted effects get no list of screens: collect them from the windows,
// since every screen has its menu bar.
function knownScreens() {
    const seen = new Map();
    for (const w of effects.stackingOrder) if (w.screen) seen.set(keyOf(w.screen), w.screen);
    return Array.from(seen.values());
}

function edgeScreen(pos, d) {
    for (const output of knownScreens()) {
        const s = output.geometry;
        if (pos.x < s.x || pos.x >= s.x + s.width || pos.y < s.y || pos.y >= s.y + s.height) continue;
        if (pos.y < s.y + s.height - EDGE) return null;
        return keyOf(output) === keyOf(d.screen) ? null : keyOf(output);
    }
    return null;
}

function stopWait() {
    if (waitId !== null) { cancel(waitId); waitId = null; }
}

function pointerMoved(pos) {
    const d = theDock();
    const key = d ? edgeScreen(pos, d) : null;
    if (!key) { pending = null; stopWait(); return; }
    if (key === pending) return;
    pending = key;
    stopWait();
    // Scripted effects have no timers: a no-op animation on the Dock times the
    // rest, and animationEnded reports when it is over.
    waitStart = Date.now();
    waitId = animate({ window: d, duration: DWELL_MS, keepAlive: false,
                       animations: [{ type: Effect.Opacity, from: 1, to: 1 }] });
}

// animationEnded does not report the id animate() returned, so the rest is
// over when an animation of the Dock ends DWELL_MS after it began.
effect.animationEnded.connect(function (w) {
    if (waitId === null || Date.now() - waitStart < DWELL_MS - 50) return;
    waitId = null;
    const d = theDock();
    if (d && pending && edgeScreen(effects.cursorPos, d) === pending) slideOut(d);
    pending = null;
});

function geometryChanged(w) {
    if (isDock(w)) {
        const key = keyOf(w.screen);
        if (dockScreen !== null && key !== dockScreen) { dockScreen = key; slideIn(w); return; }
        dockScreen = key;
    }
    refresh();
}

function watch(w) {
    if (!w || w.mttkdeDockWatched) return;
    w.mttkdeDockWatched = true;
    if (w.windowFrameGeometryChanged) w.windowFrameGeometryChanged.connect(function () { geometryChanged(w); });
    if (w.windowMaximizedStateChanged) w.windowMaximizedStateChanged.connect(refresh);
    if (w.minimizedChanged) w.minimizedChanged.connect(refresh);
    if (w.windowHiddenChanged) w.windowHiddenChanged.connect(refresh);
}

// Plasma does not move the Dock window to the new screen: it closes it and
// opens a new one there, so the slide up starts from the new window.
effects.windowAdded.connect(function (w) {
    watch(w);
    if (isDock(w)) {
        const key = keyOf(w.screen);
        const moved = dockScreen !== null && key !== dockScreen;
        dockScreen = key;
        if (moved) { slideIn(w); return; }
    }
    refresh();
});
effects.windowClosed.connect(function (w) {
    stopFlush(w);
    if (leaving && leaving.dock === w) leaving = null;
    refresh();
});
effects.desktopChanged.connect(refresh);
effects.mouseChanged.connect(function (pos) { pointerMoved(pos); });
effects.stackingOrder.forEach(watch);
{ const d = theDock(); if (d) dockScreen = keyOf(d.screen); }
refresh();
