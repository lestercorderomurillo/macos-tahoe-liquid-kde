"""Apply the theme's reviewed changes to the verified Rounded Corners source.

Upstream v0.11.0 already detects the 6.8 texture orientation (PR #547); only
desktop exclusion, native Finder edges and shared Acrylic Glass geometry remain.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path


_REPLACEMENTS = {
    "src/WindowManager.cpp": (
        ("    // Don't treat docks as windows.", """    // Desktop containment (including edit mode) must never be redirected.
    if (kwindow->isDesktop()) {
        return false;
    }

    // Don't treat docks as windows."""),
        ("    // Ignore hardcoded exceptions (KWin, lockscreen, etc.)", """    // The installer and Settings share a client-drawn window edge and corner mask.
    // Keep Acrylic Glass blur on that surface without redirecting its frame again.
    const auto classes = kwindow->windowClass().split(QLatin1Char(' '));
    if (classes.contains(QStringLiteral("org.kde.mac-tahoe-liquid-kde.settings"), Qt::CaseInsensitive) ||
        classes.contains(QStringLiteral("mac-tahoe-liquid-kde-installer"), Qt::CaseInsensitive)) {
        return false;
    }

    // Ignore hardcoded exceptions (KWin, lockscreen, etc.)"""),
    ),
    "src/Window.h": (
        ("        KWin::EffectWindow *w;", """        KWin::EffectWindow *w;
        bool nativeFinderEdge = false;"""),
    ),
    "src/Window.cpp": (
        ("    connect(Config::self(),", """    const auto klass = kwindow->windowClass().section(QLatin1Char(' '), -1);
    nativeFinderEdge = kwindow->isNormalWindow() &&
        (klass.compare(QStringLiteral("nautilus"), Qt::CaseInsensitive) == 0 ||
         klass.compare(QStringLiteral("org.gnome.Nautilus"), Qt::CaseInsensitive) == 0);
    connect(Config::self(),"""),
        ("    return (w->expandedGeometry().isValid() &&", """    return (!w->isDesktop() && !w->isDock() && w->expandedGeometry().isValid() &&"""),
    ),
    "src/Shader.h": (
        ("        int m_shader_usesNativeShadows = 0;", """        int m_shader_usesNativeShadows = 0;
        int m_shader_nativeFinderEdge = -1;"""),
    ),
    "src/Shader.cpp": (
        ('    m_shader_usesNativeShadows      =', """    m_shader_nativeFinderEdge = m_shader->uniformLocation("nativeFinderEdge");
    m_shader_usesNativeShadows      ="""),
        ("    m_shader->setUniform(m_shader_usesNativeShadows,", """    m_shader->setUniform(m_shader_nativeFinderEdge, static_cast<int>(window.nativeFinderEdge));
    m_shader->setUniform(m_shader_usesNativeShadows,"""),
    ),
    "src/shaders/shapecorners.glsl": (
        ('#include "shapecorners_shadows.glsl"', """#include "shapecorners_shadows.glsl"
uniform bool nativeFinderEdge;"""),
        ("    bool  inOutlineZone =", """    // GTK paints the hairline across the frame boundary. Sample both sides
    // of that boundary, using its actual light or dark premultiplied texels.
    float outside = distance_from_center - radius;
    if (nativeFinderEdge && usesNativeShadows && hasExpandedSize() &&
        !hasPrimaryOutline() && !hasSecondOutline() && !hasOuterOutline() && abs(angle_vector.x) > 0.1 &&
        abs(angle_vector.y) > 0.1 && outside > -2.0 && outside < 3.0) {
        vec2 inward = sign(roundness_center - start);
        vec2 tangent = clamp(roundness_center + inward * 2.0, vec2(0.5), windowSize - vec2(0.5));
        vec4 side = texture2D(sampler, pixel_to_tex(vec2(start.x - inward.x * outside, tangent.y)));
        vec4 cap = texture2D(sampler, pixel_to_tex(vec2(tangent.x, start.y - inward.y * outside)));
        vec2 direction = abs(coord0 - roundness_center);
        float capWeight = direction.y / max(direction.x + direction.y, 0.001);
        vec4 nativeEdge = mix(side, cap, capWeight);
        if (outside < 0.0) {
            return mix(tex, nativeEdge, smoothstep(-2.0, -1.0, outside));
        }
        return mix(nativeEdge, coord_shadowColor, smoothstep(1.0, 3.0, outside));
    }

    bool  inOutlineZone ="""),
    ),
    "src/Effect.cpp": (
        ('#include <QDebug>', '#include <QDebug>\n#include <QVariant>'),
        ("ShapeCorners::Effect::~Effect()\n{", """ShapeCorners::Effect::~Effect()
{
    for (auto *window : KWin::effects->stackingOrder()) {
        window->setProperty("_mttkde_corner_shape_v1", QVariant());
        window->addRepaintFull();
    }"""),
        ("    // If the shader is not valid or the window is not managed or doesn't need the effect, fall back to default.", """    // Clear stale geometry when excluded, disabled, or changing window type.
    kwindow->setProperty("_mttkde_corner_shape_v1", QVariant());

    // If the shader is not valid or the window is not managed or doesn't need the effect, fall back to default."""),
        ("    // If the window should have rounded corners, adjust the paint and opaque regions.", """    // Share the animated logical geometry with Acrylic Glass for this frame.
    // This is runtime state only: neither effect rewrites the other's settings.
    kwindow->setProperty("_mttkde_corner_shape_v1", QVariantList{
        window->hasRoundCorners() ? double(window->currentConfig.cornerRadius) : 0.0,
        Config::useSquircleShape() ? double(Config::squircleness()) : 0.0});

    // If the window should have rounded corners, adjust the paint and opaque regions."""),
        ("""    if (m_windowManager->addWindow(kwindow)) {
        // Redirect the window and set the shader if it was successfully added.
        redirect(kwindow);
        setShader(kwindow, m_shaderManager.GetShader().get());
    }""", """    // drawWindow redirects only eligible windows, after hasEffect().
    // Eager redirection also captured desktop/edit-mode surfaces (#77).
    m_windowManager->addWindow(kwindow);"""),
    ),
}


class CompatibilityError(ValueError):
    """Expose the failed path without coupling the Nix helper to a UI locale."""

    def __init__(self, relative: str):
        self.relative = relative
        super().__init__(f"Rounded Corners compatibility patch does not match {relative}")


def apply(source: Path) -> None:
    """Validate every hunk before writing; reject unexpected or partial sources."""
    updates = {}
    for relative, replacements in _REPLACEMENTS.items():
        path = source / relative
        try:
            text = path.read_text()
        except OSError as exc:
            raise CompatibilityError(relative) from exc
        for old, new in replacements:
            if text.count(new) == 1:
                continue
            if text.count(old) != 1:
                raise CompatibilityError(relative)
            text = text.replace(old, new, 1)
        updates[path] = text
    for path, text in updates.items():
        if path.read_text() != text:
            path.write_text(text)


if __name__ == "__main__":
    import sys
    apply(Path(sys.argv[1]))
