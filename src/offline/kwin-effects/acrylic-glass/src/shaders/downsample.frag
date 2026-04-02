uniform sampler2D texUnit;
uniform float offset;
uniform vec2 halfpixel;

varying vec2 uv;

void main(void)
{
    // Hexagonal disc downsample — 7-tap (center + 6 on a circle at 60° steps).
    // Produces a rounder kernel than axis-aligned Kawase, avoiding squared artifacts.
    vec4 sum = texture2D(texUnit, uv) * 4.0;
    sum += texture2D(texUnit, uv + vec2( 1.0,    0.0)   * halfpixel * offset);
    sum += texture2D(texUnit, uv + vec2( 0.5,    0.866)  * halfpixel * offset);
    sum += texture2D(texUnit, uv + vec2(-0.5,    0.866)  * halfpixel * offset);
    sum += texture2D(texUnit, uv + vec2(-1.0,    0.0)   * halfpixel * offset);
    sum += texture2D(texUnit, uv + vec2(-0.5,   -0.866)  * halfpixel * offset);
    sum += texture2D(texUnit, uv + vec2( 0.5,   -0.866)  * halfpixel * offset);

    gl_FragColor = sum / 10.0;
}
