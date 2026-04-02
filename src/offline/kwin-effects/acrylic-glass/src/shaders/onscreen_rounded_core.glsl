#version 140

#include "sdf.glsl"

uniform sampler2D texUnit;
uniform mat4 colorMatrix;
uniform float offset;
uniform vec2 halfpixel;
uniform vec4 box;
uniform vec4 cornerRadius;
uniform float opacity;
uniform vec2 blurSize;
uniform float rgbDriftStrength;
uniform float magnifyGlassStrength;
uniform float refractionWidth;
uniform float highlightWidth;
uniform float highlightStrength;
uniform float shadowStrength;

in vec2 uv;
in vec2 vertex;
out vec4 fragColor;

// MacTahoe Liquid KDE — Kpple Liquid Glass shader (core profile)

// ── SDF ───────────────────────────────────────────────────────────────────

float rrDist(vec2 p, vec2 b, vec4 cr)
{
    float r = p.x > 0.0
        ? (p.y > 0.0 ? cr.y : cr.w)
        : (p.y > 0.0 ? cr.x : cr.z);
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}

vec2 rrNormal(vec2 pos, vec2 halfB, vec4 cr)
{
    float r = pos.x > 0.0
        ? (pos.y > 0.0 ? cr.y : cr.w)
        : (pos.y > 0.0 ? cr.x : cr.z);
    vec2 q  = abs(pos) - halfB + r;
    vec2 qc = max(q, 0.0);
    float ql = length(qc);
    vec2 n  = (ql > 0.001) ? qc / ql
                            : (q.x > q.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0));
    return n * sign(pos + 0.0001);
}

// ── Gaussian blur ─────────────────────────────────────────────────────────
// Grid of SAMPLES×SAMPLES taps with Gaussian falloff so corners are de-
// weighted — eliminates the boxy look of a plain box filter.
// sigma = 0.33  →  corner weight ≈ 10 % of centre weight.
#define SAMPLES 9
#define GAUSS_SIGMA 0.33

vec3 blur_gaussian(vec2 texel, vec2 uvCenter, vec2 rect)
{
    vec4  total = vec4(0.0);
    float wsum  = 0.0;
    float step  = inversesqrt(float(SAMPLES));
    for (float i = -0.5; i <= 0.5; i += step)
    for (float j = -0.5; j <= 0.5; j += step)
    {
        float w     = exp(-(i*i + j*j) / (2.0 * GAUSS_SIGMA * GAUSS_SIGMA));
        vec2  coord = uvCenter + vec2(i, j) * rect * texel;
        total += texture(texUnit, clamp(coord, 0.0, 1.0)) * w;
        wsum  += w;
    }
    return (total / wsum).rgb;
}

// ─────────────────────────────────────────────────────────────────────────

void main()
{
    vec2 halfSize = blurSize * 0.5;
    vec2 pos      = uv * blurSize - halfSize;

    // ── Shape mask ────────────────────────────────────────────────
    // Inset by 1 px so highlight, refraction and blur never bleed
    // outside the window bounds (avoids subpixel border artifacts).
    vec2  insetHalf = halfSize - 1.0;
    float d = rrDist(pos, insetHalf, cornerRadius);
    if (d > 0.0) discard;

    vec2 outNorm = rrNormal(pos, insetHalf, cornerRadius);
    float inside = -d; // positive inside the shape

    // ── Refraction band — controls lens distortion + chromatic drift ──
    float refrBand = max(refractionWidth, 1.0);
    float edgeT    = smoothstep(-refrBand, 0.0, d);
    float edgeQ    = edgeT * edgeT; // 0 = interior, 1 = rim

    // ── Convex-lens distortion ────────────────────────────────────
    vec2  center   = vec2(0.5);
    float totalMag = magnifyGlassStrength * (1.0 + edgeQ * 3.5);
    vec2  lensUV   = center + (uv - center) * (1.0 - totalMag);

    // ── Gaussian blur base ────────────────────────────────────────
    vec2 texel = halfpixel * 2.0;
    vec3 col   = blur_gaussian(texel, lensUV, vec2(offset * 3.0));

    // ── RGB chromatic drift ───────────────────────────────────────
    // Full drift magnitude at rim — edgeQ only controls the blend
    // so the dispersion is always crisp where it appears.
    vec2  drift = outNorm * (rgbDriftStrength / blurSize);
    float rCh   = texture(texUnit, clamp(lensUV + drift,        0.0, 1.0)).r;
    float gCh   = texture(texUnit, clamp(lensUV + drift * 0.30, 0.0, 1.0)).g;
    float bCh   = texture(texUnit, clamp(lensUV - drift * 0.25, 0.0, 1.0)).b;
    col = mix(col, vec3(rCh, gCh, bCh), edgeQ);

    // ── Specular rim highlight (independent highlightWidth band) ──
    float hlBand  = max(highlightWidth, 1.0);
    float rimSoft = smoothstep(0.0, hlBand,        inside) * (1.0 - smoothstep(hlBand * 0.5, hlBand * 2.0, inside));
    float rimPeak = smoothstep(0.0, 2.0,            inside) * (1.0 - smoothstep(2.0,           6.0,          inside));

    float litFacing = dot(outNorm, normalize(vec2(-0.5, -1.0)));
    float litT      = 0.30 + 0.70 * clamp(litFacing, 0.0, 1.0);

    float specI = ((rimSoft * 0.20 + rimPeak * 0.80) * litT + rimPeak * 0.10) * highlightStrength;
    col = mix(col, vec3(0.87, 0.93, 1.0), clamp(specI, 0.0, 0.95));

    // ── Ambient gradient (top bright / bottom shadow) ─────────────
    // Extent in UV derived from highlightWidth in pixels.
    float hlUV = highlightWidth / blurSize.y;
    col += max(0.0, hlUV - uv.y)              * 0.06 * shadowStrength;
    col  = max(col - max(0.0, uv.y - (1.0 - hlUV)) * 0.04 * shadowStrength, 0.0);

    // ── Composite ─────────────────────────────────────────────────
    float mask = 1.0 - smoothstep(-1.5, -0.5, d);
    fragColor  = vec4(col, mask) * colorMatrix * opacity;
}
