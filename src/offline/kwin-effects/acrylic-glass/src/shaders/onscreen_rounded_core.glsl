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
    float edgeBand = min(halfSize.x, halfSize.y) * 0.15;
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

    // 4. Concave lens — subtle magnification near borders
    vec2 center = vec2(0.5);
    vec2 fromCenter = uv - center;
    float magnify = 0.012 * edgeCurve;
    vec2 baseUV = center + fromCenter * (1.0 - magnify);

    // 5. Chromatic aberration — smooth spectral gradient along SDF contour
    vec2 caDir = refractDir * 22.0 * edgeCurve / blurSize;

    // 6. Spectral sampling: 5 positions for visible RGB prismatic separation
    vec3 c0 = texture(texUnit, clamp(baseUV - caDir,            0.0, 1.0)).rgb;
    vec3 c1 = texture(texUnit, clamp(baseUV - caDir * 0.5,      0.0, 1.0)).rgb;
    vec3 c2 = texture(texUnit, clamp(baseUV,                    0.0, 1.0)).rgb;
    vec3 c3 = texture(texUnit, clamp(baseUV + caDir * 0.5,      0.0, 1.0)).rgb;
    vec3 c4 = texture(texUnit, clamp(baseUV + caDir,            0.0, 1.0)).rgb;

    // Spectral weights — red at one end, blue at other, green centered
    vec3 spectral;
    spectral.r = c0.r*0.05 + c1.r*0.15 + c2.r*0.25 + c3.r*0.35 + c4.r*0.20;
    spectral.g = c0.g*0.10 + c1.g*0.25 + c2.g*0.30 + c3.g*0.25 + c4.g*0.10;
    spectral.b = c0.b*0.20 + c1.b*0.35 + c2.b*0.25 + c3.b*0.15 + c4.b*0.05;

    // Mix: vivid spectral at edges, neutral center
    vec3 sharp = mix(c2, spectral, 0.85 * edgeCurve);

    // 9-tap kawase blur — stronger base for warmer center glow
    float blurScale = offset * 3.0 * (1.0 + edgeCurve * 4.0);
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
