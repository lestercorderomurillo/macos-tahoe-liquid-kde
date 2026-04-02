#version 140

uniform sampler2D texUnit;
uniform float offset;
uniform vec2 halfpixel;

in vec2 uv;

out vec4 fragColor;

void main(void)
{
    // Hexagonal disc downsample — 7-tap (center + 6 on a circle at 60° steps).
    // Produces a rounder kernel than axis-aligned Kawase, avoiding squared artifacts.
    vec4 sum = texture(texUnit, uv) * 4.0;
    sum += texture(texUnit, uv + vec2( 1.0,    0.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2( 0.5,    0.866)  * halfpixel * offset);
    sum += texture(texUnit, uv + vec2(-0.5,    0.866)  * halfpixel * offset);
    sum += texture(texUnit, uv + vec2(-1.0,    0.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2(-0.5,   -0.866)  * halfpixel * offset);
    sum += texture(texUnit, uv + vec2( 0.5,   -0.866)  * halfpixel * offset);

    fragColor = sum / 10.0;
}
