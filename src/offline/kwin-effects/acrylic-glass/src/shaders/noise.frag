#include "sdf.glsl"

uniform vec4 box;
uniform vec4 cornerRadius;
uniform float opacity;
uniform sampler2D texUnit;
uniform vec2 noiseTextureSize;

varying vec2 uv;
varying vec2 vertex;

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

    gl_FragColor = vec4(texture2D(texUnit, uvNoise).rrr * (mask * opacity), 0);
}
