#extension GL_OES_standard_derivatives : enable

#include "sdf.glsl"

uniform sampler2D texUnit;
uniform mat4 colorMatrix;
uniform float offset;
uniform vec2 halfpixel;
uniform vec4 box;
uniform vec4 cornerRadius;
uniform float opacity;

varying vec2 uv;
varying vec2 vertex;

#include "glass.glsl"

// Surface normal from SDF — models curved glass edge with circular cross-section
vec3 glassNormal(float sd, float t)
{
    float dx = dFdx(sd);
    float dy = dFdy(sd);
    float nc = clamp((t + sd) / t, 0.0, 1.0);
    float ns = sqrt(1.0 - nc * nc);
    return normalize(vec3(dx * nc, dy * nc, ns));
}

// Glass surface height — circular cross-section at the edge
float glassHeight(float sd, float t)
{
    if (sd >= 0.0) return 0.0;
    if (sd < -t) return t;
    float x = t + sd;
    return sqrt(t * t - x * x);
}

void main(void)
{
    vec2 halfBlurSize = blurSize * 0.5;
    float minHalfSize = min(halfBlurSize.x, halfBlurSize.y);

    vec2 position = uv * blurSize - halfBlurSize.xy;
    float dist = roundedRectangleDist(position, halfBlurSize, cornerRadius);

    if (dist >= 0.0) {
        float df = fwidth(dist);
        gl_FragColor = texture2D(texUnit, uv) * (1.0 - clamp(0.5 + dist / df, 0.0, 1.0));
        return;
    }

    // Glass refraction — SDF-based surface normal + Snell's law via refract()
    // Refraction follows the actual window shape including rounded corners
    const float refractiveIndex = 1.5;
    float thickness = 48.0;
    float baseHeight = 75.0;

    vec3 normal = glassNormal(dist, thickness);
    // Blend normal toward center so top/bottom refraction isn't straight like a mirror
    vec2 toCenter = -normalize(position + vec2(0.001));
    normal.xy = mix(normal.xy, toCenter * length(normal.xy), 0.25);
    normal = normalize(normal);

    vec3 refractVec = refract(vec3(0.0, 0.0, -1.0), normal, 1.0 / refractiveIndex);
    float h = glassHeight(dist, thickness);
    float denom = dot(vec3(0.0, 0.0, -1.0), refractVec);
    float refractLen = abs(denom) > 0.001 ? (h + baseHeight) / denom : 0.0;
    vec2 refractedUV = uv + refractVec.xy * refractLen / blurSize;

    // Border proximity from SDF
    float borderBand = minHalfSize * 0.25;
    float borderFactor = smoothstep(-borderBand, 0.0, dist);

    // Blur: subtle at center, heavy at edges
    float scaledOffset = offset * (1.0 + borderFactor * 4.0);

    // Kawase upsample with refraction + stronger blur near edges
    vec4 sum = texture2D(texUnit, clamp(refractedUV + vec2(-halfpixel.x * 2.0, 0.0) * scaledOffset, 0.0, 1.0));
    sum += texture2D(texUnit, clamp(refractedUV + vec2(-halfpixel.x, halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum += texture2D(texUnit, clamp(refractedUV + vec2(0.0, halfpixel.y * 2.0) * scaledOffset, 0.0, 1.0));
    sum += texture2D(texUnit, clamp(refractedUV + vec2(halfpixel.x, halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum += texture2D(texUnit, clamp(refractedUV + vec2(halfpixel.x * 2.0, 0.0) * scaledOffset, 0.0, 1.0));
    sum += texture2D(texUnit, clamp(refractedUV + vec2(halfpixel.x, -halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum += texture2D(texUnit, clamp(refractedUV + vec2(0.0, -halfpixel.y * 2.0) * scaledOffset, 0.0, 1.0));
    sum += texture2D(texUnit, clamp(refractedUV + vec2(-halfpixel.x, -halfpixel.y) * scaledOffset, 0.0, 1.0)) * 2.0;
    sum /= 12.0;

    // Chromatic aberration — wide RGB split at borders, low mix to preserve blur
    vec2 caDir = refractVec.xy * refractLen * 0.2 / blurSize;
    float caStrength = borderFactor * 0.25;
    sum.r = mix(sum.r, texture2D(texUnit, clamp(refractedUV + caDir, 0.0, 1.0)).r, caStrength);
    sum.b = mix(sum.b, texture2D(texUnit, clamp(refractedUV - caDir, 0.0, 1.0)).b, caStrength);

    // Border highlight — follows SDF shape including corner radius
    float borderPx = -dist;
    float borderHighlight = smoothstep(0.0, 2.0, borderPx) * (1.0 - smoothstep(2.0, 6.0, borderPx));
    sum.rgb += borderHighlight * 0.08;

    // Reflection — Fresnel at left/right edges only (horizontal normal)
    float fresnel = abs(normal.x) * 2.0;
    sum.rgb = mix(sum.rgb, vec3(1.0), fresnel * 0.08);

    // Gradient lighting — glass catches light at top
    float normInside = clamp(-dist / minHalfSize, 0.0, 1.0);
    sum.rgb += mix(0.04, 0.0, uv.y) * normInside;

    sum = glass(sum, cornerRadius);

    float f = sdfRoundedBox(vertex, box.xy, box.zw, cornerRadius);
    float df = fwidth(f);
    sum *= 1.0 - clamp(0.5 + f / df, 0.0, 1.0);

    gl_FragColor = sum * colorMatrix * opacity;
}
