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

function isPanel(w) { return w && w.caption === PANEL; }

function opened(w) {
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
