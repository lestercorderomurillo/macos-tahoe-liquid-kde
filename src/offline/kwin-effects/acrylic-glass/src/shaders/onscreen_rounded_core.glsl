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

in vec2 uv;
in vec2 vertex;

out vec4 fragColor;

#include "glass.glsl"

void main(void)
{
    vec2 halfBlurSize = blurSize * 0.5;
    float minHalfSize = min(halfBlurSize.x, halfBlurSize.y);

    vec2 position = uv * blurSize - halfBlurSize;
    float dist = roundedRectangleDist(position, halfBlurSize, cornerRadius);

    if (dist >= 0.0) {
        float df = fwidth(dist);
        fragColor = texture(texUnit, uv) * (1.0 - clamp(0.5 + dist / df, 0.0, 1.0));
        return;
    }

    vec2 fromCenter = uv - 0.5;

    // Glass refraction — curved glass pulls edges inward (Snell's law approx)
    // n=1.5 (crown glass), displacement ~ (n-1) * r², quadratic falloff
    const float refractiveIndex = 1.5;
    float r2 = dot(fromCenter, fromCenter) * 4.0;
    vec2 refractedUV = uv - fromCenter * (refractiveIndex - 1.0) * r2 * 0.3;

    // Border proximity from SDF
    float borderBand = minHalfSize * 0.25;
    float borderFactor = smoothstep(-borderBand, 0.0, dist);

    // More blur near edges — scale kawase offset up to 3x at border
    float scaledOffset = offset * (1.0 + borderFactor * 2.0);

    // Kawase upsample with refraction + stronger blur near edges
    vec4 sum = texture(texUnit, clamp(refractedUV + vec2(-halfpixel.x * 2.0, 0.0) * scaledOffset, 0.0, 1.0));
    sum += texture(texUnit, clamp(refractedUV + vec2(-halfpixel.x, halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum += texture(texUnit, clamp(refractedUV + vec2(0.0, halfpixel.y * 2.0) * scaledOffset, 0.0, 1.0));
    sum += texture(texUnit, clamp(refractedUV + vec2(halfpixel.x, halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum += texture(texUnit, clamp(refractedUV + vec2(halfpixel.x * 2.0, 0.0) * scaledOffset, 0.0, 1.0));
    sum += texture(texUnit, clamp(refractedUV + vec2(halfpixel.x, -halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum += texture(texUnit, clamp(refractedUV + vec2(0.0, -halfpixel.y * 2.0) * scaledOffset, 0.0, 1.0));
    sum += texture(texUnit, clamp(refractedUV + vec2(-halfpixel.x, -halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum /= 12.0;

    // Chromatic aberration — proportional to distance from center
    vec2 caOffset = 0.01 * fromCenter;
    sum.r = mix(sum.r, texture(texUnit, clamp(refractedUV + caOffset, 0.0, 1.0)).r, 0.5);
    sum.b = mix(sum.b, texture(texUnit, clamp(refractedUV - caOffset, 0.0, 1.0)).b, 0.5);

    // Border highlight — follows SDF shape including corner radius
    float borderPx = -dist;
    float borderHighlight = smoothstep(0.0, 2.0, borderPx) * (1.0 - smoothstep(2.0, 6.0, borderPx));
    sum.rgb += borderHighlight * 0.08;

    // Gradient lighting — glass catches light at top
    float normInside = clamp(-dist / minHalfSize, 0.0, 1.0);
    sum.rgb += mix(0.03, 0.0, uv.y) * normInside;

    sum = glass(sum, cornerRadius);
    float f = sdfRoundedBox(vertex, box.xy, box.zw, cornerRadius);
    float df = fwidth(f);
    sum *= 1.0 - clamp(0.5 + f / df, 0.0, 1.0);

    fragColor = sum * colorMatrix * opacity;
}
