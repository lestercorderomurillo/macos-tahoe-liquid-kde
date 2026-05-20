// MacTahoe Liquid KDE — Acrylic Glass highlight helpers

#ifndef LIQUIDGLASS_HIGHLIGHT_GLSL
#define LIQUIDGLASS_HIGHLIGHT_GLSL

// Y-axis-agnostic angular weight: brighter where outNorm faces "up",
// softer at the sides, dimmer on the bottom. Reference shader uses
// sin(atan(y, x) - phase) which is the same idea, simplified here to
// a direct dot product against a fixed "up" direction in normal-space
// (rim is in normalised coords already after the SDF normal call).
// 0.65..1.20 envelope keeps the rim visible everywhere but lit on top.
float lgRimAngularWeight(vec2 outNorm)
{
    // outNorm.y > 0 means the surface point sits on the upper half of
    // the rim. We don't know KWin's Y convention statically (varies by
    // GL profile / framebuffer orientation), so the envelope is gentle
    // enough that an inverted Y still reads as "slightly directional"
    // rather than "rim is on the wrong side". If the lit side ends up
    // visually inverted we can flip the sign here.
    return 0.65 + 0.55 * clamp(outNorm.y * 0.5 + 0.5, 0.0, 1.0);
}

vec3 lgApplyHighlight(vec3 color, float inside, vec2 outNorm,
                      float highlightWidth, float highlightStrength)
{
    float band = max(highlightWidth, 1.0);
    float rim = exp(-inside * (3.0 / band)) * smoothstep(0.0, 2.0, inside);
    float intensity = rim * highlightStrength * lgRimAngularWeight(outNorm);
    return mix(color, vec3(0.87, 0.93, 1.0), clamp(intensity, 0.0, 0.95));
}

#endif
