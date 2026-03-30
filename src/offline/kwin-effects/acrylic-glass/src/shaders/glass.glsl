// MacTahoe Liquid KDE — Acrylic Glass shader

float roundedRectangleDist(vec2 p, vec2 b, vec4 cornerRadius)
{
    float r = p.x > 0.0
        ? (p.y > 0.0 ? cornerRadius.y : cornerRadius.w)
        : (p.y > 0.0 ? cornerRadius.x : cornerRadius.z);
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}

vec4 roundedRectangle(vec2 fragCoord, vec3 texture, vec4 cornerRadius)
{
    vec2 halfblurSize = blurSize * 0.5;
    vec2 p = fragCoord - halfblurSize;
    float dist = roundedRectangleDist(p, halfblurSize, cornerRadius);

    if (dist <= 0.0) {
        return vec4(texture, 1.0);
    }

    float s = smoothstep(0.0, 1.0, dist);
    return vec4(texture, mix(1.0, 0.0, s));
}

vec4 glass(vec4 sum, vec4 cornerRadius)
{
    return roundedRectangle(uv * blurSize, sum.rgb, cornerRadius);
}
