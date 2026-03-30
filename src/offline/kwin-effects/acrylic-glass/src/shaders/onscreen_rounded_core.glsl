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

void main(void)
{
    vec2 halfSize = blurSize * 0.5;
    vec2 position = uv * blurSize - halfSize;
    
    float d = roundedRectangleDist(position, halfSize, cornerRadius);
    // Gradiente radial para rotación 360° sin costuras
    vec2 vGrad = normalize(vec2(dFdx(d), dFdy(d)));

    // Antialiasing exterior
    float edgeAlpha = 1.0 - smoothstep(-1.0, 1.0, d);
    if (edgeAlpha <= 0.0) discard;

    // 1. Grosor del borde aumentado (Edge Zone)
    // Usamos un multiplicador para que el efecto entre más hacia el centro que los 22pt
    float edgeZone = cornerRadius.x * 3.5; 
    float distFactor = clamp(-d / edgeZone, 0.0, 1.0);
    
    // Curva de inclinación: pow(x, 0.8) hace que el borde sea más "gordo" y presente
    float tilt = pow(1.0 - distFactor, 0.8); 
    vec3 normal = normalize(vec3(vGrad * tilt, 1.0 - tilt));

    // 2. Refracción Base
    const float ior = 1.45;
    vec3 refractVec = refract(vec3(0.0, 0.0, -1.0), normal, 1.0 / ior);
    
    // Fuerza de distorsión (h)
    float h = 70.0 * tilt;
    vec2 baseRefUV = uv + (refractVec.xy * h / blurSize);

    // 3. ABERRACIÓN CROMÁTICA VIVA (RGB Separación)
    // Dispersión: cuánto se separan los colores. Aumenta este valor para más color.
    float dispersion = 0.015 * tilt; 
    
    vec2 uvR = uv + (refractVec.xy * (h * (1.0 + dispersion)) / blurSize);
    vec2 uvG = baseRefUV;
    vec2 uvB = uv + (refractVec.xy * (h * (1.0 - dispersion)) / blurSize);

    // 4. Muestreo Kawase con Offset RGB (Simplificado para performance, manteniendo calidad)
    float blurScale = offset * (1.0 + tilt * 2.5);
    
    // Función auxiliar interna para blur por canal
    #define SAMPLE_CA(uv_target) (texture(texUnit, clamp(uv_target, 0.0, 1.0)).rgb)
    
    vec3 color;
    color.r = texture(texUnit, clamp(uvR, 0.0, 1.0)).r;
    color.g = texture(texUnit, clamp(uvG, 0.0, 1.0)).g;
    color.b = texture(texUnit, clamp(uvB, 0.0, 1.0)).b;

    // Aplicamos el Blur (Kawase) sobre el color base ya separado
    // Para máximo "RGB vivo", el blur debe ser ligeramente menor que la separación
    vec2 bOffset = halfpixel * blurScale;
    vec4 sum = vec4(color, 1.0) * 4.0;
    sum.rgb += texture(texUnit, clamp(uvG + vec2(bOffset.x, bOffset.y), 0.0, 1.0)).rgb * 2.0;
    sum.rgb += texture(texUnit, clamp(uvG - vec2(bOffset.x, bOffset.y), 0.0, 1.0)).rgb * 2.0;
    sum.rgb /= 8.0;

    // 5. Tint y Brillo (Espejo)
    // Fresnel para el reflejo blanco en el borde curvo
    float fresnel = pow(tilt, 2.5);
    sum.rgb += vec3(0.2, 0.25, 0.3) * fresnel; // Brillo con ligero tinte azulado/frío
    
    // Tint global superior (aumentado para visibilidad)
    sum.rgb += mix(0.12, 0.0, uv.y) * (1.0 - tilt);

    // 6. Finalizado
    sum = glass(sum, cornerRadius);
    float finalMask = 1.0 - smoothstep(-0.5, 0.5, d);
    
    fragColor = sum * colorMatrix * (opacity * finalMask);
}
