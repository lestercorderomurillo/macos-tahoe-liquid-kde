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

void main()
{
    vec2 halfSize = blurSize * 0.5;
    vec2 pos = uv * blurSize - halfSize;

    // 1. SDF rounded rectangle (22pt)
    float d = roundedRectangleDist(pos, halfSize, cornerRadius);

    float edgeAlpha = 1.0 - smoothstep(-1.0, 1.0, d);
    if (edgeAlpha <= 0.0) discard;

    // 2. Edge proximity: 0=interior, 1=border
    float edgeBand = min(halfSize.x, halfSize.y) * 0.35;
    float edge = smoothstep(-edgeBand, 0.0, d);
    float edgeCurve = pow(edge, 2.5);

    // 3. Analytical SDF gradient — curves with rounded corners )(
    float r = pos.x > 0.0
        ? (pos.y > 0.0 ? cornerRadius.y : cornerRadius.w)
        : (pos.y > 0.0 ? cornerRadius.x : cornerRadius.z);
    vec2 q = abs(pos) - halfSize + r;
    vec2 qc = max(q, 0.0);
    float qLen = length(qc);
    vec2 refractDir = (qLen > 0.001)
        ? qc / qLen
        : (q.x > q.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0));
    refractDir *= sign(pos + vec2(0.0001));

    // 4. Concave lens — image grows near borders
    vec2 center = vec2(0.5);
    vec2 fromCenter = uv - center;
    float magnify = 0.03 * edgeCurve;
    vec2 baseUV = center + fromCenter * (1.0 - magnify);

    // 5. Chromatic aberration — follows SDF contour )(, vivid RGB
    vec2 caDir = refractDir * 15.0 * edgeCurve / blurSize;

    // 6. Sample: center=sharp (direct texture), edges=gaussian blur
    //    Mix between sharp sample and 9-tap kawase based on edge proximity
    vec3 sharp = vec3(0.0);
    sharp.r = texture(texUnit, clamp(baseUV + caDir, 0.0, 1.0)).r;
    sharp.g = texture(texUnit, clamp(baseUV,         0.0, 1.0)).g;
    sharp.b = texture(texUnit, clamp(baseUV - caDir, 0.0, 1.0)).b;

    // 9-tap kawase upsample for gaussian blur at edges
    float blurScale = offset * (1.0 + edgeCurve * 5.0);
    vec2 hp = halfpixel * blurScale;

    vec3 blur  = texture(texUnit, clamp(baseUV + vec2(-hp.x * 2.0, 0.0),  0.0, 1.0)).rgb;
    blur += texture(texUnit, clamp(baseUV + vec2(-hp.x,  hp.y),           0.0, 1.0)).rgb * 2.0;
    blur += texture(texUnit, clamp(baseUV + vec2( 0.0,   hp.y * 2.0),     0.0, 1.0)).rgb;
    blur += texture(texUnit, clamp(baseUV + vec2( hp.x,  hp.y),           0.0, 1.0)).rgb * 2.0;
    blur += texture(texUnit, clamp(baseUV + vec2( hp.x * 2.0, 0.0),       0.0, 1.0)).rgb;
    blur += texture(texUnit, clamp(baseUV + vec2( hp.x, -hp.y),           0.0, 1.0)).rgb * 2.0;
    blur += texture(texUnit, clamp(baseUV + vec2( 0.0,  -hp.y * 2.0),     0.0, 1.0)).rgb;
    blur += texture(texUnit, clamp(baseUV + vec2(-hp.x, -hp.y),           0.0, 1.0)).rgb * 2.0;
    blur /= 12.0;

    // 7. Mix: center=sharp crystal, edges=gaussian blur
    vec3 col = mix(sharp, blur, edgeCurve);

    // 8. Bevel — subtle highlight top-left, shadow bottom-right
    float rim = pow(edge, 5.0);
    float bevel = dot(normalize(pos + vec2(0.0001)), vec2(-0.707, -0.707));
    col += vec3(0.7, 0.8, 1.0) * max(bevel, 0.0) * rim * 0.06;
    col *= 1.0 - max(-bevel, 0.0) * rim * 0.04;

    // 9. Final
    vec4 finalColor = vec4(col, 1.0);
    finalColor = glass(finalColor, cornerRadius);

    float finalMask = 1.0 - smoothstep(-0.5, 0.5, d);
    fragColor = finalColor * colorMatrix * (opacity * finalMask);
}
