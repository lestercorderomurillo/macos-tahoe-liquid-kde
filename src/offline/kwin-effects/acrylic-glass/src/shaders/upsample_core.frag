#version 140

uniform sampler2D texUnit;
uniform float offset;
uniform vec2 halfpixel;

in vec2 uv;

out vec4 fragColor;

void main(void)
{
    // Hexagonal disc upsample — two concentric rings for a circular, lens-like blur.
    // Inner ring: 6 taps at r=1, 60° steps (weight 2).
    // Outer ring: 6 taps at r=2, 30° offset (weight 1).
    vec4 sum  = texture(texUnit, uv + vec2( 1.0,    0.0)   * halfpixel * offset) * 2.0;
    sum += texture(texUnit, uv + vec2( 0.5,    0.866)  * halfpixel * offset) * 2.0;
    sum += texture(texUnit, uv + vec2(-0.5,    0.866)  * halfpixel * offset) * 2.0;
    sum += texture(texUnit, uv + vec2(-1.0,    0.0)   * halfpixel * offset) * 2.0;
    sum += texture(texUnit, uv + vec2(-0.5,   -0.866)  * halfpixel * offset) * 2.0;
    sum += texture(texUnit, uv + vec2( 0.5,   -0.866)  * halfpixel * offset) * 2.0;

    sum += texture(texUnit, uv + vec2( 1.732,  1.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2( 0.0,    2.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2(-1.732,  1.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2(-1.732, -1.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2( 0.0,   -2.0)   * halfpixel * offset);
    sum += texture(texUnit, uv + vec2( 1.732, -1.0)   * halfpixel * offset);

    fragColor = sum / 18.0;
}
