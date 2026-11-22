// SPDX-License-Identifier: GPL-3.0-or-later
// macOS Tahoe Control Center transitions, run entirely by the compositor so
// they stay at display rate whatever the panel's own frame cost.
// Open: zoom 1.015 -> 1 and fade in over 150 ms, decelerating.
// Close: the closed window zooms 1 -> 1.015 and fades out over 120 ms, accelerating.
// Liquid Glass is forced on the panel so its lenses and backdrop follow the zoom.
"use strict";

// Values chosen on the tuning bench.
const OPEN_MS = 150;
const CLOSE_MS = 120;
const ZOOM = 1.015;
const PANEL = "mttkde-control-center";
const SEARCH = "mttkde-search";

function fadeSearch(w, opening) {
    if (effects.hasActiveFullScreenEffect || (opening ? !w.visible : w.skipsCloseAnimation)) return;

    // Supersede Plasma's generic popup transition for this capsule.
    const role = opening ? Effect.WindowAddedGrabRole : Effect.WindowClosedGrabRole;
    effect.grab(w, role, true);
    const duration = animationTime(opening ? OPEN_MS : CLOSE_MS);

    if (opening) {
        w.searchFadeIn = animate({
            window: w,
            duration: duration,
            curve: QEasingCurve.OutCubic,
            type: Effect.Opacity,
            from: 0.0,
            to: 1.0
        });
        w.searchFadeStarted = Date.now();
        w.searchFadeDuration = duration;
    } else {
        let opacity = 1.0;
        if (w.searchFadeIn) {
            const elapsed = Date.now() - w.searchFadeStarted;
            const progress = Math.min(1, elapsed / Math.max(1, w.searchFadeDuration));
            opacity = 1 - Math.pow(1 - progress, 3);
            cancel(w.searchFadeIn);
            delete w.searchFadeIn;
        }
        animate({
            window: w,
            duration: duration,
            curve: QEasingCurve.InCubic,
            type: Effect.Opacity,
            from: opacity,
            to: 0.0,
            keepAlive: true
        });
    }
}

function isPanel(w) { return w && w.caption === PANEL; }

function opened(w) {
    if (w && w.caption === SEARCH) {
        fadeSearch(w, true);
        return;
    }
    if (!isPanel(w)) return;
    // Claim the window so Plasma's sliding popup does not also animate it.
    w.setData(Effect.WindowAddedGrabRole, effect);
    w.setData(Effect.WindowClosedGrabRole, effect);
    // Liquid Glass skips scaled windows unless forced.
    w.setData(Effect.WindowForceBlurRole, true);
    animate({
        window: w,
        duration: OPEN_MS,
        curve: QEasingCurve.OutCubic,
        animations: [
            { type: Effect.Scale, from: ZOOM, to: 1.0 },
            { type: Effect.Opacity, from: 0.0, to: 1.0 }
        ]
    });
}

function closed(w) {
    if (w && w.caption === SEARCH) {
        fadeSearch(w, false);
        return;
    }
    if (!isPanel(w)) return;
    w.setData(Effect.WindowClosedGrabRole, effect);
    // A finite animation releases the closed window once it ends.
    animate({
        window: w,
        duration: CLOSE_MS,
        curve: QEasingCurve.InCubic,
        keepAlive: true,
        animations: [
            { type: Effect.Scale, from: 1.0, to: ZOOM },
            { type: Effect.Opacity, from: 1.0, to: 0.0 }
        ]
    });
}

effects.windowAdded.connect(opened);
effects.windowClosed.connect(closed);
