// MacTahoe Liquid KDE — Acrylic Glass lens + chromatic distortion helpers

#ifndef LIQUIDGLASS_DISTORT_GLSL
#define LIQUIDGLASS_DISTORT_GLSL

vec2 lgLensUV(vec2 uv, float magnifyGlassStrength, float edgeQ)
{
    // Edge-gated lens. The previous formula
    //   totalMag = magnifyGlassStrength * (1.0 + edgeQ * 3.5)
    // bled the magnification into the centre of the window — at the
    // default magnifyGlassStrength=0.03 every pixel got a 3% inward
    // pull, so ~30 screen pixels collapsed to ~29 source texels. With
    // GL_LINEAR + the per-fragment snap-to-texel passthrough, that
    // produced the "crisp but temporally unstable, looks like 0.5"
    // artifact whenever the window moved by a single device pixel.
    //
    // Multiplying by edgeQ instead of adding 1.0 to it means the centre
    // (edgeQ=0) is now identity → snap returns the exact source texel,
    // pixel-perfect across frames. The rim (edgeQ≈1) still gets the
    // full magnification (4.5×, matching the previous peak value at
    // the edge: 1.0 + 3.5*1 = 4.5).
    vec2 center = vec2(0.5);
    float totalMag = magnifyGlassStrength * edgeQ * 4.5;
    return center + (uv - center) * (1.0 - totalMag);
}

vec3 lgApplyRgbDrift(sampler2D texUnit,
                     vec3 baseColor,
                     vec2 lensUV,
                     vec2 outwardNormal,
                     vec2 blurSizePx,
                     float rgbDriftStrength,
                     float edgeQ)
{
    vec2 safeSize = max(blurSizePx, vec2(1.0));
    vec2 drift = outwardNormal * (rgbDriftStrength / safeSize);

    float r = LG_SAMPLE(texUnit, clamp(lensUV + drift, 0.0, 1.0)).r;
    float g = LG_SAMPLE(texUnit, clamp(lensUV + drift * 0.30, 0.0, 1.0)).g;
    float b = LG_SAMPLE(texUnit, clamp(lensUV - drift * 0.25, 0.0, 1.0)).b;

    return mix(baseColor, vec3(r, g, b), edgeQ);
}

#endif
