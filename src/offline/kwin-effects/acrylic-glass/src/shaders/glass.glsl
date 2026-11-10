#extension GL_OES_standard_derivatives : enable

#define LG_SAMPLE(tex, coord) texture2D(tex, coord)
#define LG_OUT gl_FragColor

#include "sdf.glsl"
#include "blur.glsl"
#include "distort.glsl"
#include "highlight.glsl"

uniform sampler2D texUnit;
uniform mat4 colorMatrix;
uniform float offset;
uniform vec2 halfpixel;
uniform vec4 box;
uniform vec4 cornerRadius;
uniform float opacity;
uniform float rgbDriftStrength;
uniform float magnifyGlassStrength;
uniform float refractionWidth;
uniform float highlightWidth;
uniform float highlightStrength;
uniform float centerOpacity;
uniform bool dockSurface;
uniform vec2 backgroundSize;
uniform vec4 gradientTop;
uniform vec4 gradientCenter;
uniform float gradientCenterPosition;
uniform vec4 gradientBottom;
uniform bool darkGradientOverlay;

varying vec2 uv;
varying vec2 vertex;

void main(void)
{
    vec2 halfSize = blurSize * 0.5;
    vec2 localPos = uv - box.xy;

    float d = lgRoundedRectDistance(localPos, halfSize, cornerRadius);
    float mask = lgRoundedRectCoverage(d);
    if (mask <= 0.0) {
        discard;
    }

    vec2 outNorm = lgRoundedRectNormal(localPos, halfSize, cornerRadius);
    float inside = max(-d, 0.0);

    float refrBand = max(refractionWidth * (dockSurface ? 1.25 : 1.0), 1.0);
    float edgeT = smoothstep(-refrBand, 0.0, d);
    // Keep the Dock's refraction near the rim.
    // Both profiles leave the centre undistorted.
    float edgeQ = edgeT * edgeT * (dockSurface ? 1.0 : edgeT);

    vec2 safeBackgroundSize = max(backgroundSize, vec2(1.0));
    vec2 backgroundUV = vec2(vertex.x / safeBackgroundSize.x, 1.0 - vertex.y / safeBackgroundSize.y);
    vec2 lensCenter = vec2(box.x / safeBackgroundSize.x, 1.0 - box.y / safeBackgroundSize.y);
    vec2 lensUV = backgroundUV;
    if (magnifyGlassStrength > 0.0) {
        lensUV = dockSurface
            ? lgDockLensUV(backgroundUV, outNorm, localPos, blurSize, safeBackgroundSize, magnifyGlassStrength, edgeQ)
            : lgLensUV(backgroundUV, lensCenter, magnifyGlassStrength, edgeQ);
    }
    vec2 texel = halfpixel * 2.0;
    vec3 col;
    if (offset > 0.0) {
        col = lgGaussianBlur(texUnit, texel, lensUV);
    } else {
        // Pixel-exact passthrough: snap to texel center so GL_LINEAR returns
        // the underlying texel exactly instead of a sub-pixel bilinear blend.
        vec2 snapped = (floor(lensUV / texel) + 0.5) * texel;
        col = LG_SAMPLE(texUnit, clamp(snapped, 0.0, 1.0)).rgb;
    }
    if (rgbDriftStrength > 0.0) {
        col = lgApplyRgbDrift(texUnit, col, lensUV, outNorm, blurSize, rgbDriftStrength, edgeQ);
    }
    if (highlightStrength > 0.0) {
        col = lgApplyHighlight(col, inside, outNorm, highlightWidth, highlightStrength, dockSurface);
    }

    vec4 surface = vec4(col, 1.0) * colorMatrix;
    if (darkGradientOverlay) {
        // Frame-local geometry keeps top/bottom upright on all backends.
        // Tint changes color only: the bottom retains the same blurred glass.
        float heightFraction = clamp((localPos.y + halfSize.y) / max(blurSize.y, 1.0), 0.0, 1.0);
        // End positions collapse one segment without dividing by zero.
        float centerPosition = clamp(gradientCenterPosition, 0.0, 1.0);
        bool upper = heightFraction < centerPosition;
        vec4 start = upper ? gradientTop : gradientCenter;
        vec4 end = upper ? gradientCenter : gradientBottom;
        float segmentStart = upper ? 0.0 : centerPosition;
        float segmentLength = upper ? centerPosition : 1.0 - centerPosition;
        float t = smoothstep(0.0, 1.0,
            (heightFraction - segmentStart) / max(segmentLength, 0.000001));
        float tintAlpha = mix(start.a, end.a, t);
        vec3 tint = mix(start.rgb * start.a, end.rgb * end.a, t);
        surface.rgb = surface.rgb * (1.0 - tintAlpha) + tint;
    }
    // Only the Dock reveals sharp backdrop through its centre. Applet popups
    // need full blur coverage behind their thin client fills.
    float coverage = (dockSurface ? mix(centerOpacity, 1.0, edgeQ) : 1.0);
    LG_OUT = surface * (mask * opacity * coverage);
}
