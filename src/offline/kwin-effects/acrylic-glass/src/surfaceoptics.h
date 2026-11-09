// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

struct SurfaceOptics {
    float rgbDrift;
    float refraction;
    float refractionWidth;
    float highlightWidth;
    float highlightStrength;
};

inline SurfaceOptics opticsForSurface(bool dock, SurfaceOptics configured)
{
    // v0.62.0 defaults, including its Dock-only RGB attenuation.
    return dock ? SurfaceOptics{12.0f * 0.24f, 0.1f, 18.0f, 3.5f, 0.1f} : configured;
}
