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
uniform int blurType;

varying vec2 uv;
varying vec2 vertex;

void main(void)
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
    // Cubic rim concentration — refraction / RGB drift / lens distortion fall
    // off sharply away from the edge, leaving the centre of the glass clean.
    // The day9 reference shader uses pow(...,20) for the same intent on its
    // SDF demo; cubic is the conservative analogue for a window-sized effect.
    float edgeQ = edgeT * edgeT * edgeT;

    vec2 lensUV = (magnifyGlassStrength > 0.0)
        ? lgLensUV(uv, magnifyGlassStrength, edgeQ)
        : uv;
    vec2 texel = halfpixel * 2.0;
    vec3 col;
    if (offset > 0.0) {
        col = lgBlurDispatch(blurType, texUnit, texel, lensUV, vec2(offset * 3.0));
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
        col = lgApplyHighlight(col, inside, outNorm, highlightWidth, highlightStrength);
    }

    float mask = 1.0 - smoothstep(-3.0, 0.0, d);
    LG_OUT = vec4(col, mask) * colorMatrix * opacity;
}
