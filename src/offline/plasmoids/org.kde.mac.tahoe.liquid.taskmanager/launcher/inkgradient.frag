#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
};
layout(binding = 1) uniform sampler2D source;
layout(binding = 2) uniform sampler2D ramp;
void main()
{
    vec4 original = texture(source, qt_TexCoord0);
    vec4 ink = texture(ramp, qt_TexCoord0);
    vec3 rgb = ink.a > 0.0 ? ink.rgb * (original.a / ink.a) : original.rgb;
    fragColor = vec4(rgb, original.a) * qt_Opacity;
}
