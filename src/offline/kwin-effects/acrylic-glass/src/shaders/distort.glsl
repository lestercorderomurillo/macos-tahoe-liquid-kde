// MacTahoe Liquid KDE — Acrylic Glass lens + chromatic distortion helpers

#ifndef LIQUIDGLASS_DISTORT_GLSL
#define LIQUIDGLASS_DISTORT_GLSL

vec2 lgLensUV(vec2 uv, float magnifyGlassStrength, float edgeQ)
{
    vec2 center = vec2(0.5);
    float totalMag = magnifyGlassStrength * (1.0 + edgeQ * 3.5);
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
