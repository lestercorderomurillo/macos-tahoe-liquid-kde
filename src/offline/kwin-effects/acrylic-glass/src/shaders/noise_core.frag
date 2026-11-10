#version 140

#include "sdf.glsl"

uniform vec4 box;
uniform vec4 cornerRadius;
uniform float opacity;
uniform sampler2D texUnit;
uniform vec2 noiseTextureSize;

in vec2 uv;
in vec2 vertex;

out vec4 fragColor;

void main(void)
{
    vec2 halfSize = blurSize * 0.5;
    vec2 pos = vertex - box.xy;
    float d = lgRoundedRectDistance(pos, halfSize, cornerRadius);
    float mask = lgRoundedRectCoverage(d);
    if (mask <= 0.0) {
        discard;
    }
    vec2 uvNoise = vec2(gl_FragCoord.xy / noiseTextureSize);

    fragColor = vec4(texture(texUnit, uvNoise).rrr * (mask * opacity), 0);
}
