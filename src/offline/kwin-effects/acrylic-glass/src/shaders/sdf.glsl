// MacTahoe Liquid KDE — Acrylic Glass SDF helpers

#ifndef LIQUIDGLASS_SDF_GLSL
#define LIQUIDGLASS_SDF_GLSL

uniform vec2 blurSize;

float lgRoundedRectDistance(vec2 p, vec2 halfSize, vec4 cornerRadius)
{
    float r = p.x > 0.0
        ? (p.y > 0.0 ? cornerRadius.y : cornerRadius.w)
        : (p.y > 0.0 ? cornerRadius.x : cornerRadius.z);
    vec2 q = abs(p) - halfSize + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}

vec2 lgRoundedRectNormal(vec2 p, vec2 halfSize, vec4 cornerRadius)
{
    float r = p.x > 0.0
        ? (p.y > 0.0 ? cornerRadius.y : cornerRadius.w)
        : (p.y > 0.0 ? cornerRadius.x : cornerRadius.z);
    vec2 q = abs(p) - halfSize + r;
    vec2 qc = max(q, 0.0);
    float ql = length(qc);
    vec2 n = (ql > 0.001)
        ? qc / ql
        : (q.x > q.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0));
    return n * sign(p + 0.0001);
}

#endif
