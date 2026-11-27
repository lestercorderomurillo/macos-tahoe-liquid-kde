// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

struct SurfaceOptics {
    float rgbDrift;
    float refraction;
    float refractionWidth;
    float highlightWidth;
    float highlightStrength;
    // Inward edge lens depth in logical pixels (0 = disabled). The rim samples
    // the backdrop this far inside, easing out across RefractionWidth.
    float edgeLens = 0;
    // Shadow falloff outside the controls, in logical pixels.
    float backdropGap = 0;
    float backdropFeather = 0;
    float backdropShadow = 0;
    float backdropCurve = 1;
    // 0 keeps the surface interior sharp while preserving the edge lens.
    float surfaceBlur = 1;
    // Fade of the backdrop over this many pixels below its top edge, where the
    // window meets the menu bar, so no line shows there.
    float backdropTopFade = 0;
};
