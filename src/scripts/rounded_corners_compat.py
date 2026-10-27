"""Apply the theme's reviewed changes to the verified Rounded Corners source.

Upstream v0.11.0 already detects the 6.8 texture orientation (PR #547); only
desktop exclusion and the shared corner shape for Acrylic Glass remain.
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
    ),
    "src/Window.cpp": (
        ("    return (w->expandedGeometry().isValid() &&", """    return (!w->isDesktop() && !w->isDock() && w->expandedGeometry().isValid() &&"""),
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
