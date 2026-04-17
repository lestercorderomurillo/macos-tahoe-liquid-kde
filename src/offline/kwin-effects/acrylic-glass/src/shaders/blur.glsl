// MacTahoe Liquid KDE — Acrylic Glass blur helpers

#ifndef LIQUIDGLASS_BLUR_GLSL
#define LIQUIDGLASS_BLUR_GLSL

// Grid of SAMPLES×SAMPLES taps with Gaussian falloff so corners are de-weighted.
#define LG_GAUSS_SAMPLES 9
#define LG_GAUSS_SIGMA 0.33

vec3 lgGaussianBlur(sampler2D texUnit, vec2 texel, vec2 uvCenter, vec2 rect)
{
    vec4 total = vec4(0.0);
    float weightSum = 0.0;
    float step = inversesqrt(float(LG_GAUSS_SAMPLES));

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

#endif
