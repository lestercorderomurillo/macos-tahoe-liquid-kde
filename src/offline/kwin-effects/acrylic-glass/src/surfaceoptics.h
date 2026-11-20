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
    // Seamless backdrop under multi-surface panels (0 feather = disabled):
    // fully blurred up to backdropGap outside the surfaces, then faded out.
    float backdropGap = 0;
    float backdropFeather = 0;
    // Shadow-like backdrop: how much of the blurred backdrop shows at full
    // coverage (0 = sharp desktop), how dark it gets, and the falloff exponent.
    float backdropBlurMix = 1;
    float backdropShadow = 0;
    float backdropCurve = 1;
    // 0 keeps the backdrop sharp behind the surfaces (lens only); the blur then
    // only serves the backdrop shadow around them.
    float surfaceBlur = 1;
    // Fade of the backdrop over this many pixels below its top edge, where the
    // window meets the menu bar, so no line shows there.
    float backdropTopFade = 0;
};
