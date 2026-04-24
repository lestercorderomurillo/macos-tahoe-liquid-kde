#version 140

#define LG_SAMPLE(tex, coord) texture(tex, coord)
#define LG_OUT fragColor

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

in vec2 uv;
in vec2 vertex;
out vec4 fragColor;

void main()
{
    vec2 halfSize = blurSize * 0.5;
    vec2 pos = uv * blurSize - halfSize;

    // Inset by 1 px so highlight/refraction never bleed outside the window.
    vec2 insetHalf = max(halfSize - vec2(1.0), vec2(0.5));
    float d = lgRoundedRectDistance(pos, insetHalf, cornerRadius);
    if (d > 0.0) {
        discard;
    }

    vec2 outNorm = lgRoundedRectNormal(pos, insetHalf, cornerRadius);
    float inside = -d;

    float refrBand = max(refractionWidth, 1.0);
    float edgeT = smoothstep(-refrBand, 0.0, d);
    float edgeQ = edgeT * edgeT;

    vec2 lensUV = lgLensUV(uv, magnifyGlassStrength, edgeQ);
    vec2 texel = halfpixel * 2.0;
    vec3 col = lgGaussianBlur(texUnit, texel, lensUV, vec2(offset * 3.0));
    col = lgApplyRgbDrift(texUnit, col, lensUV, outNorm, blurSize, rgbDriftStrength, edgeQ);
    col = lgApplyHighlight(col, inside, highlightWidth, highlightStrength);

    float mask = 1.0 - smoothstep(-3.0, 0.0, d);
    LG_OUT = vec4(col, mask) * colorMatrix * opacity;
}
