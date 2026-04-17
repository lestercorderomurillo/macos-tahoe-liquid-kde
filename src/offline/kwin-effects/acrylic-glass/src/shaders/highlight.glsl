// MacTahoe Liquid KDE — Acrylic Glass highlight helpers

#ifndef LIQUIDGLASS_HIGHLIGHT_GLSL
#define LIQUIDGLASS_HIGHLIGHT_GLSL

vec3 lgApplyHighlight(vec3 color, float inside, float highlightWidth, float highlightStrength)
{
    float band = max(highlightWidth, 1.0);
    float rim = exp(-inside * (3.0 / band)) * smoothstep(0.0, 2.0, inside);
    float intensity = rim * highlightStrength;
    return mix(color, vec3(0.87, 0.93, 1.0), clamp(intensity, 0.0, 0.95));
}

#endif
