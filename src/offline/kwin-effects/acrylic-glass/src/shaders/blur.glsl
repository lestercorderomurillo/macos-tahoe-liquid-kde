// MacTahoe Liquid KDE — Acrylic Glass blur helpers

#ifndef LIQUIDGLASS_BLUR_GLSL
#define LIQUIDGLASS_BLUR_GLSL

// Shared SAMPLES×SAMPLES tap grid used by every kernel below.
#define LG_BLUR_SAMPLES 9
#define LG_GAUSS_SIGMA 0.33

// Blur type IDs — must mirror the AcrylicGlassType enum order in glass.kcfg.
#define LG_BLUR_GAUSSIAN 0
#define LG_BLUR_BOX      1
#define LG_BLUR_LENS     2

// Box and Lens reach further than Gaussian so their kernel shape can dominate
// the already-Kawase-smoothed input. Tuned so the three modes are clearly
// distinguishable at the same BlurStrength.
#define LG_BOX_RADIUS_SCALE  6.0
#define LG_LENS_RADIUS_SCALE 7.0
// Bokeh highlight boost: brighter taps weigh more, producing the lens-blur
// signature glow on out-of-focus highlights.
#define LG_LENS_HIGHLIGHT_GAIN 12.0
#define LG_LENS_HIGHLIGHT_POW  4.0

// Gaussian: per-tap weight falls off with distance from center.
vec3 lgGaussianBlur(sampler2D texUnit, vec2 texel, vec2 uvCenter, vec2 rect)
{
    vec4 total = vec4(0.0);
    float weightSum = 0.0;
    float step = inversesqrt(float(LG_BLUR_SAMPLES));

    for (float i = -0.5; i <= 0.5; i += step)
    for (float j = -0.5; j <= 0.5; j += step)
    {
        float weight = exp(-(i * i + j * j) / (2.0 * LG_GAUSS_SIGMA * LG_GAUSS_SIGMA));
        vec2 coord = uvCenter + vec2(i, j) * rect * texel;
        total += LG_SAMPLE(texUnit, clamp(coord, 0.0, 1.0)) * weight;
        weightSum += weight;
    }

    return (total / max(weightSum, 0.0001)).rgb;
}

// Box: every tap inside a wider square contributes equally — flatter, frosted look.
vec3 lgBoxBlur(sampler2D texUnit, vec2 texel, vec2 uvCenter, vec2 rect)
{
    vec4 total = vec4(0.0);
    float weightSum = 0.0;
    float step = inversesqrt(float(LG_BLUR_SAMPLES));
    vec2 wideRect = rect * LG_BOX_RADIUS_SCALE;

    for (float i = -0.5; i <= 0.5; i += step)
    for (float j = -0.5; j <= 0.5; j += step)
    {
        vec2 coord = uvCenter + vec2(i, j) * wideRect * texel;
        total += LG_SAMPLE(texUnit, clamp(coord, 0.0, 1.0));
        weightSum += 1.0;
    }

    return (total / max(weightSum, 0.0001)).rgb;
}

// Lens (bokeh): disc kernel with brightness-weighted taps so highlights bloom.
vec3 lgLensBlur(sampler2D texUnit, vec2 texel, vec2 uvCenter, vec2 rect)
{
    vec4 total = vec4(0.0);
    float weightSum = 0.0;
    float step = inversesqrt(float(LG_BLUR_SAMPLES));
    vec2 wideRect = rect * LG_LENS_RADIUS_SCALE;

    for (float i = -0.5; i <= 0.5; i += step)
    for (float j = -0.5; j <= 0.5; j += step)
    {
        if ((i * i + j * j) > 0.25) continue;
        vec2 coord = uvCenter + vec2(i, j) * wideRect * texel;
        vec4 s = LG_SAMPLE(texUnit, clamp(coord, 0.0, 1.0));
        float luma = dot(s.rgb, vec3(0.299, 0.587, 0.114));
        float weight = 1.0 + pow(luma, LG_LENS_HIGHLIGHT_POW) * LG_LENS_HIGHLIGHT_GAIN;
        total += s * weight;
        weightSum += weight;
    }

    return (total / max(weightSum, 0.0001)).rgb;
}

vec3 lgBlurDispatch(int blurType, sampler2D texUnit, vec2 texel, vec2 uvCenter, vec2 rect)
{
    if (blurType == LG_BLUR_BOX)  return lgBoxBlur(texUnit, texel, uvCenter, rect);
    if (blurType == LG_BLUR_LENS) return lgLensBlur(texUnit, texel, uvCenter, rect);
    return lgGaussianBlur(texUnit, texel, uvCenter, rect);
}

#endif
