/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-FileCopyrightText: 2011 Philipp Knechtges <philipp-dev@knechtges.com>
    SPDX-FileCopyrightText: 2018 Alex Nemeth <alex.nemeth329@gmail.com>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "effect.h"
#include "surfaceoptics.h"
#include "build_identity.h"
// KConfigSkeleton
#include "glassconfig.h"
#include "roundedblurshape.h"

#include "core/pixelgrid.h"
#include "core/rendertarget.h"
#include "core/renderviewport.h"
#include "effect/effecthandler.h"
#include "opengl/glplatform.h"
#include "opengl/eglcontext.h"
#include "scene/decorationitem.h"
#include "scene/scene.h"
#include "scene/surfaceitem.h"
#include "scene/windowitem.h"
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
// Plasma 6.7 merged blur + contrast into one background-effect protocol;
// the dedicated blur.h / contrast.h managers are gone. Blur is announced
// through waylandServer()->backgroundEffectManager() instead.
#include "wayland/backgroundeffect_v1.h"
#include "wayland_server.h"
#else
#include "wayland/blur.h"
#include "wayland/contrast.h"
#endif
#include "wayland/display.h"
#include "wayland/surface.h"
#include "window.h"

#if KWIN_BUILD_X11
#include "utils/xcbutils.h"
#include <xcb/render.h>
#endif

#include <QGuiApplication>
#include <QMatrix4x4>
#include <QObject>
#include <QPalette>
#include "gradientcolors.h"
#include <QScreen>
#include <QTime>
#include <QTimer>
#include <QWindow>
#include <algorithm>
#include <array>
#include <cmath> // for ceil()
#include <cstdlib>
#include <climits>
#include <vector>

#include <KConfigGroup>
#include <KSharedConfig>

#include <KDecoration3/Decoration>

Q_LOGGING_CATEGORY(KWIN_BLUR, "kwin_effect_liquidglass", QtWarningMsg)

// File-scope helpers

/// One-shot Qt resource initialiser. Called from the constructor so the
/// :/effects/liquidglass/* paths resolve at runtime.
static void ensureResources()
{
    Q_INIT_RESOURCE(liquidglass);
}

static QString shaderPath(const QString& name, const QString& extension)
{
    // KWin 6.7+ loads the requested file verbatim and translates modern
    // GLSL for the active context. Legacy attribute/varying syntax fails
    // on the GLES 3 context used by KWin 6.8.
#if ACRYLIC_GLASS_KWIN_6_7
    return QStringLiteral(MTTKDE_GLASS_RESOURCE_PREFIX "shaders/") + name + QStringLiteral("_core.") + extension;
#else
    return QStringLiteral(MTTKDE_GLASS_RESOURCE_PREFIX "shaders/") + name + QStringLiteral(".") + extension;
#endif
}

namespace KWin {

QString BlurEffect::debug(const QString &parameter) const
{
    if (parameter == QStringLiteral("status")) {
        return m_valid ? QStringLiteral("ready") : QStringLiteral("shader-error");
    }
    return QStringLiteral(MTTKDE_GLASS_BUILD_ID);
}

#if ACRYLIC_GLASS_KWIN_6_7
/// 6.7 removed the global scaledRect() helper (it lived in
/// effect/globals.h pre-6.7). Re-provide it verbatim so the three call
/// sites below stay version-agnostic.
inline QRectF scaledRect(const QRectF& rect, qreal scale)
{
    return QRectF{rect.x() * scale, rect.y() * scale, rect.width() * scale, rect.height() * scale};
}
#endif

/// 6.8 removed snapToPixelGrid / snapToPixelGridF (replaced by the
/// scale-aware snapToPixels in core/pixelgrid.h). Re-provide the old
/// round-both-corners semantics under local names so every KWin
/// version resolves the same implementation.
inline QRectF agSnapToPixelGridF(const QRectF& rect)
{
    return QRectF(QPointF(std::round(rect.left()), std::round(rect.top())),
                  QPointF(std::round(rect.right()), std::round(rect.bottom())));
}

inline QRect agSnapToPixelGrid(const QRectF& rect)
{
    const QPoint topLeft(std::round(rect.left()), std::round(rect.top()));
    const QPoint bottomRight(std::round(rect.right()), std::round(rect.bottom()));
    return QRect(topLeft.x(), topLeft.y(), bottomRight.x() - topLeft.x(), bottomRight.y() - topLeft.y());
}

namespace {

GLVertex2D interpolateVertex(const GLVertex2D& from, const GLVertex2D& to, float factor)
{
    return GLVertex2D{
        .position = from.position + (to.position - from.position) * factor,
        .texcoord = from.texcoord + (to.texcoord - from.texcoord) * factor,
    };
}

std::vector<GLVertex2D> clipPolygonToRect(const std::vector<GLVertex2D>& polygon, const QRectF& rect)
{
    using EdgeTest = bool (*)(const QVector2D&, const QRectF&);
    using EdgeIntersection = float (*)(const QVector2D&, const QVector2D&, const QRectF&);
    struct Edge
    {
        EdgeTest inside;
        EdgeIntersection factor;
    };
    static constexpr Edge edges[] = {
        {
            [](const QVector2D& point, const QRectF& clip) { return point.x() >= clip.left(); },
            [](const QVector2D& from, const QVector2D& to, const QRectF& clip) {
                return static_cast<float>((clip.left() - from.x()) / (to.x() - from.x()));
            },
        },
        {
            [](const QVector2D& point, const QRectF& clip) { return point.x() <= clip.right(); },
            [](const QVector2D& from, const QVector2D& to, const QRectF& clip) {
                return static_cast<float>((clip.right() - from.x()) / (to.x() - from.x()));
            },
        },
        {
            [](const QVector2D& point, const QRectF& clip) { return point.y() >= clip.top(); },
            [](const QVector2D& from, const QVector2D& to, const QRectF& clip) {
                return static_cast<float>((clip.top() - from.y()) / (to.y() - from.y()));
            },
        },
        {
            [](const QVector2D& point, const QRectF& clip) { return point.y() <= clip.bottom(); },
            [](const QVector2D& from, const QVector2D& to, const QRectF& clip) {
                return static_cast<float>((clip.bottom() - from.y()) / (to.y() - from.y()));
            },
        },
    };

    std::vector<GLVertex2D> output = polygon;
    for (const Edge& edge : edges) {
        if (output.empty()) {
            break;
        }

        std::vector<GLVertex2D> input;
        input.swap(output);
        GLVertex2D previous = input.back();
        bool previousInside = edge.inside(previous.position, rect);
        for (const GLVertex2D& current : input) {
            const bool currentInside = edge.inside(current.position, rect);
            if (currentInside != previousInside) {
                const float factor = std::clamp(edge.factor(previous.position, current.position, rect), 0.0f, 1.0f);
                output.push_back(interpolateVertex(previous, current, factor));
            }
            if (currentInside) {
                output.push_back(current);
            }
            previous = current;
            previousInside = currentInside;
        }
    }
    return output;
}

float triangleArea(const GLVertex2D& a, const GLVertex2D& b, const GLVertex2D& c)
{
    return (b.position.x() - a.position.x()) * (c.position.y() - a.position.y())
        - (b.position.y() - a.position.y()) * (c.position.x() - a.position.x());
}

void appendTriangleFan(std::vector<GLVertex2D>& vertices, const std::vector<GLVertex2D>& polygon)
{
    if (polygon.size() < 3) {
        return;
    }
    for (size_t i = 1; i + 1 < polygon.size(); ++i) {
        if (std::abs(triangleArea(polygon[0], polygon[i], polygon[i + 1])) <= 0.0001f) {
            continue;
        }
        vertices.push_back(polygon[0]);
        vertices.push_back(polygon[i]);
        vertices.push_back(polygon[i + 1]);
    }
}

void appendClippedTriangle(std::vector<GLVertex2D>& vertices, const std::array<GLVertex2D, 3>& triangle,
    const std::vector<QRectF>& clipRects)
{
    if (clipRects.empty()) {
        vertices.insert(vertices.end(), triangle.begin(), triangle.end());
        return;
    }

    const std::vector<GLVertex2D> polygon(triangle.begin(), triangle.end());
    for (const QRectF& clipRect : clipRects) {
        appendTriangleFan(vertices, clipPolygonToRect(polygon, clipRect));
    }
}

} // namespace

/// X11 atom name we listen to for the blur-behind property protocol.
static const QByteArray s_blurAtomName = QByteArrayLiteral("_KDE_NET_WM_BLUR_BEHIND_REGION");

#if KWIN_BUILD_X11
#if defined(GLASS_X11)
static bool hasAlphaVisual(xcb_connection_t* connection, xcb_visualid_t visual)
{
    static QHash<xcb_visualid_t, bool> cache;
    if (const auto it = cache.constFind(visual); it != cache.cend()) {
        return it.value();
    }
    const auto formatsCookie = xcb_render_query_pict_formats(connection);
    const std::unique_ptr<xcb_render_query_pict_formats_reply_t, decltype(&std::free)> formats(
        xcb_render_query_pict_formats_reply(connection, formatsCookie, nullptr), &std::free);
    if (!formats) {
        return false;
    }
    bool alphaVisual = false;
    auto screens = xcb_render_query_pict_formats_screens_iterator(formats.get());
    for (; screens.rem && !alphaVisual; xcb_render_pictscreen_next(&screens)) {
        auto depths = xcb_render_pictscreen_depths_iterator(screens.data);
        for (; depths.rem && !alphaVisual; xcb_render_pictdepth_next(&depths)) {
            auto visuals = xcb_render_pictdepth_visuals_iterator(depths.data);
            for (; visuals.rem; xcb_render_pictvisual_next(&visuals)) {
                if (visuals.data->visual != visual) {
                    continue;
                }
                auto pictFormats = xcb_render_query_pict_formats_formats_iterator(formats.get());
                for (; pictFormats.rem; xcb_render_pictforminfo_next(&pictFormats)) {
                    if (pictFormats.data->id == visuals.data->format
                        && pictFormats.data->direct.alpha_mask != 0) {
                        alphaVisual = true;
                        break;
                    }
                }
                break;
            }
        }
    }
    cache.insert(visual, alphaVisual);
    return alphaVisual;
}
#endif
#endif

// Static singleton storage (definitions live here, declarations in .h).
// The protocol-manager singletons only exist on the pre-6.7 API; 6.7
// registers a capability on the shared backgroundEffectManager instead.
#if !ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
BlurManagerInterface* BlurEffect::s_blurManager = nullptr;
QTimer* BlurEffect::s_blurManagerRemoveTimer = nullptr;

ContrastManagerInterface* BlurEffect::s_contrastManager = nullptr;
QTimer* BlurEffect::s_contrastManagerRemoveTimer = nullptr;
#endif

// Colour-transform helper

/// Build the saturation × contrast × brightness 4×4 colour matrix used
/// by the onscreen pass. Each component degenerates to identity when
/// its input is exactly 1.0 (qFuzzyCompare-tolerant), so the call site
/// can pass through user-tuned values without branching itself.
///
/// Luminance weights follow the BT.709 standard (0.2126/0.7152/0.0722)
/// — same convention KWin's default blur effect uses, so chained
/// effects stay perceptually consistent.
static QMatrix4x4 colorTransformMatrix(qreal saturation, qreal contrast, qreal brightness)
{
    QMatrix4x4 saturationMatrix;
    QMatrix4x4 contrastMatrix;
    QMatrix4x4 brightnessMatrix;

    if (!qFuzzyCompare(saturation, 1.0)) {
        const qreal rval = (1.0 - saturation) * 0.2126;
        const qreal gval = (1.0 - saturation) * 0.7152;
        const qreal bval = (1.0 - saturation) * 0.0722;

        saturationMatrix = QMatrix4x4(
            rval + saturation, rval, rval, 0.0, gval, gval + saturation, gval, 0.0, bval, bval, bval + saturation, 0.0, 0.0, 0.0, 0.0, 1.0);
    }

    if (!qFuzzyCompare(contrast, 1.0)) {
        const float transl = (1.0 - contrast) / 2.0;

        contrastMatrix = QMatrix4x4(contrast, 0.0, 0.0, 0.0, 0.0, contrast, 0.0, 0.0, 0.0, 0.0, contrast, 0.0, transl, transl, transl, 1.0);
    }

    if (!qFuzzyCompare(brightness, 1.0)) {
        brightnessMatrix.scale(brightness, brightness, brightness);
    }

    return contrastMatrix * saturationMatrix * brightnessMatrix;
}

BlurEffect::BlurEffect()
{
    BlurConfig::instance(effects->config());
    ensureResources();

    // Onscreen pass: SDF + drift + lens + rim, the user-facing surface
    m_roundedOnscreenPass.shader = ShaderManager::instance()->generateShaderFromFile(
        ShaderTrait::MapTexture, shaderPath(QStringLiteral("glass"), QStringLiteral("vert")), shaderPath(QStringLiteral("glass"), QStringLiteral("frag")));
    if (!m_roundedOnscreenPass.shader) {
        qCWarning(KWIN_BLUR) << "Failed to load onscreen pass shader (null)";
        return;
#if !ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
        // GLShader::isValid() was removed in 6.7; a null return from
        // generateShaderFromFile is the only failure signal there.
    } else if (!m_roundedOnscreenPass.shader->isValid()) {
        qCWarning(KWIN_BLUR) << "Onscreen pass shader compiled but is NOT valid";
        return;
#endif
    } else {
        m_roundedOnscreenPass.mvpMatrixLocation = m_roundedOnscreenPass.shader->uniformLocation("modelViewProjectionMatrix");
        m_roundedOnscreenPass.colorMatrixLocation = m_roundedOnscreenPass.shader->uniformLocation("colorMatrix");
        m_roundedOnscreenPass.offsetLocation = m_roundedOnscreenPass.shader->uniformLocation("offset");
        m_roundedOnscreenPass.halfpixelLocation = m_roundedOnscreenPass.shader->uniformLocation("halfpixel");
        m_roundedOnscreenPass.boxLocation = m_roundedOnscreenPass.shader->uniformLocation("box");
        m_roundedOnscreenPass.cornerSquircleLocation = m_roundedOnscreenPass.shader->uniformLocation("cornerSquircle");
        m_roundedOnscreenPass.cornerRadiusLocation = m_roundedOnscreenPass.shader->uniformLocation("cornerRadius");
        m_roundedOnscreenPass.opacityLocation = m_roundedOnscreenPass.shader->uniformLocation("opacity");
        m_roundedOnscreenPass.blurSizeLocation = m_roundedOnscreenPass.shader->uniformLocation("blurSize");
        m_roundedOnscreenPass.rgbDriftStrengthLocation = m_roundedOnscreenPass.shader->uniformLocation("rgbDriftStrength");
        m_roundedOnscreenPass.magnifyGlassStrengthLocation = m_roundedOnscreenPass.shader->uniformLocation("magnifyGlassStrength");
        m_roundedOnscreenPass.refractionWidthLocation = m_roundedOnscreenPass.shader->uniformLocation("refractionWidth");
        m_roundedOnscreenPass.highlightWidthLocation = m_roundedOnscreenPass.shader->uniformLocation("highlightWidth");
        m_roundedOnscreenPass.highlightStrengthLocation = m_roundedOnscreenPass.shader->uniformLocation("highlightStrength");
        m_roundedOnscreenPass.darkGradientOverlayLocation = m_roundedOnscreenPass.shader->uniformLocation("darkGradientOverlay");
        m_roundedOnscreenPass.centerOpacityLocation = m_roundedOnscreenPass.shader->uniformLocation("centerOpacity");
        m_roundedOnscreenPass.dockSurfaceLocation = m_roundedOnscreenPass.shader->uniformLocation("dockSurface");
        m_roundedOnscreenPass.backgroundSizeLocation = m_roundedOnscreenPass.shader->uniformLocation("backgroundSize");
        m_roundedOnscreenPass.gradientTopLocation = m_roundedOnscreenPass.shader->uniformLocation("gradientTop");
        m_roundedOnscreenPass.gradientCenterLocation = m_roundedOnscreenPass.shader->uniformLocation("gradientCenter");
        m_roundedOnscreenPass.gradientCenterPositionLocation = m_roundedOnscreenPass.shader->uniformLocation("gradientCenterPosition");
        m_roundedOnscreenPass.gradientBottomLocation = m_roundedOnscreenPass.shader->uniformLocation("gradientBottom");

        qCDebug(KWIN_BLUR) << "Onscreen shader uniforms:"
                           << "mvp=" << m_roundedOnscreenPass.mvpMatrixLocation << "color=" << m_roundedOnscreenPass.colorMatrixLocation
                           << "offset=" << m_roundedOnscreenPass.offsetLocation << "halfpx=" << m_roundedOnscreenPass.halfpixelLocation
                           << "box=" << m_roundedOnscreenPass.boxLocation << "corner=" << m_roundedOnscreenPass.cornerRadiusLocation
                           << "opacity=" << m_roundedOnscreenPass.opacityLocation << "blurSize=" << m_roundedOnscreenPass.blurSizeLocation;
    }

    // Dual Kawase downsample pass
    m_downsamplePass.shader = ShaderManager::instance()->generateShaderFromFile(
        ShaderTrait::MapTexture, shaderPath(QStringLiteral("vertex"), QStringLiteral("vert")), shaderPath(QStringLiteral("downsample"), QStringLiteral("frag")));
    if (!m_downsamplePass.shader) {
        qCWarning(KWIN_BLUR) << "Failed to load downsampling pass shader";
        return;
    } else {
        m_downsamplePass.mvpMatrixLocation = m_downsamplePass.shader->uniformLocation("modelViewProjectionMatrix");
        m_downsamplePass.offsetLocation = m_downsamplePass.shader->uniformLocation("offset");
        m_downsamplePass.halfpixelLocation = m_downsamplePass.shader->uniformLocation("halfpixel");
    }

    // Dual Kawase upsample pass
    m_upsamplePass.shader = ShaderManager::instance()->generateShaderFromFile(
        ShaderTrait::MapTexture, shaderPath(QStringLiteral("vertex"), QStringLiteral("vert")), shaderPath(QStringLiteral("upsample"), QStringLiteral("frag")));
    if (!m_upsamplePass.shader) {
        qCWarning(KWIN_BLUR) << "Failed to load upsampling pass shader";
        return;
    } else {
        m_upsamplePass.mvpMatrixLocation = m_upsamplePass.shader->uniformLocation("modelViewProjectionMatrix");
        m_upsamplePass.offsetLocation = m_upsamplePass.shader->uniformLocation("offset");
        m_upsamplePass.halfpixelLocation = m_upsamplePass.shader->uniformLocation("halfpixel");
    }

    // Noise pass (grain over the blurred result)
    m_noisePass.shader = ShaderManager::instance()->generateShaderFromFile(
        ShaderTrait::MapTexture, shaderPath(QStringLiteral("glass"), QStringLiteral("vert")), shaderPath(QStringLiteral("noise"), QStringLiteral("frag")));
    if (!m_noisePass.shader) {
        qCWarning(KWIN_BLUR) << "Failed to load noise pass shader";
        return;
    } else {
        m_noisePass.mvpMatrixLocation = m_noisePass.shader->uniformLocation("modelViewProjectionMatrix");
        m_noisePass.boxLocation = m_noisePass.shader->uniformLocation("box");
        m_noisePass.blurSizeLocation = m_noisePass.shader->uniformLocation("blurSize");
        m_noisePass.cornerRadiusLocation = m_noisePass.shader->uniformLocation("cornerRadius");
        m_noisePass.cornerSquircleLocation = m_noisePass.shader->uniformLocation("cornerSquircle");
        m_noisePass.opacityLocation = m_noisePass.shader->uniformLocation("opacity");
        m_noisePass.noiseTextureSizeLocation = m_noisePass.shader->uniformLocation("noiseTextureSize");
    }

    // Initial config read
    initBlurStrengthValues();
    reconfigure(ReconfigureAll);

#if KWIN_BUILD_X11
    // X11: announce the blur-behind property atom
    if (effects->xcbConnection()) {
        net_wm_blur_region = effects->announceSupportProperty(s_blurAtomName, this);
    }
#endif

    // Announce blur support to clients. Only under a Wayland session:
    // effects->waylandDisplay() is null on pure X11, where surface blur
    // comes from the net_wm_blur_region atom path above instead.
    if (effects->waylandDisplay()) {
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
        // Plasma 6.7: a single capability flag on the shared
        // background-effect manager replaces the per-protocol singletons.
        // Contrast/saturation is no longer a separate protocol.
        waylandServer()->backgroundEffectManager()->addBlurCapability();
#else
        // Pre-6.7: dedicated blur + contrast manager singletons, with
        // deferred teardown. The *ManagerInterface ctors dereference the
        // display immediately — so an unguarded `new` segfaults the effect
        // at load on X11 logins (hence the waylandDisplay() guard above).
        // Matches upstream Better Blur.
        if (!s_blurManagerRemoveTimer) {
            s_blurManagerRemoveTimer = new QTimer(QCoreApplication::instance());
            s_blurManagerRemoveTimer->setSingleShot(true);
            s_blurManagerRemoveTimer->callOnTimeout([]() {
                s_blurManager->remove();
                s_blurManager = nullptr;
            });
        }
        s_blurManagerRemoveTimer->stop();
        if (!s_blurManager) {
            s_blurManager = new BlurManagerInterface(effects->waylandDisplay(), s_blurManagerRemoveTimer);
        }

        if (!s_contrastManagerRemoveTimer) {
            s_contrastManagerRemoveTimer = new QTimer(QCoreApplication::instance());
            s_contrastManagerRemoveTimer->setSingleShot(true);
            s_contrastManagerRemoveTimer->callOnTimeout([]() {
                s_contrastManager->remove();
                s_contrastManager = nullptr;
            });
        }
        s_contrastManagerRemoveTimer->stop();
        if (!s_contrastManager) {
            s_contrastManager = new ContrastManagerInterface(effects->waylandDisplay(), s_contrastManagerRemoveTimer);
        }
#endif
    }

    // EffectsHandler signal wiring
    connect(effects, &EffectsHandler::windowAdded, this, &BlurEffect::slotWindowAdded);
    connect(effects, &EffectsHandler::windowDeleted, this, &BlurEffect::slotWindowDeleted);
#if !defined(GLASS_X11)
    connect(effects, &EffectsHandler::viewRemoved, this, &BlurEffect::slotViewRemoved);
#endif
#if KWIN_BUILD_X11
    connect(effects, &EffectsHandler::propertyNotify, this, &BlurEffect::slotPropertyNotify);
    connect(effects, &EffectsHandler::xcbConnectionChanged, this, [this]() { net_wm_blur_region = effects->announceSupportProperty(s_blurAtomName, this); });
#endif

    // Prime the blur regions for windows that already exist at startup —
    // slotWindowAdded normally fires for new windows only.
    const auto stackingOrder = effects->stackingOrder();
    for (EffectWindow* window : stackingOrder) {
        slotWindowAdded(window);
    }

    m_valid = true;
}

/// Tear down the blur announcement. On pre-6.7 we defer manager removal —
/// KWin restarts compositing on backend swaps and recreating the
/// BlurManagerInterface immediately would race the surface teardown; the
/// 1 s settle window matches the upstream blur effect. On 6.7 the
/// capability flag is just dropped from the shared manager.
BlurEffect::~BlurEffect()
{
    // Shader failure returns before this instance announces blur support.
    // It must not revoke another effect's capability during recovery.
    if (!m_valid) {
        return;
    }
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
    if (waylandServer()) {
        waylandServer()->backgroundEffectManager()->removeBlurCapability();
    }
#else
    if (s_blurManager) {
        s_blurManagerRemoveTimer->start(1000);
    }

    if (s_contrastManager) {
        s_contrastManagerRemoveTimer->start(1000);
    }
#endif
}

// Configuration

/// Populate the (iteration × offset × expandSize) lookup tables that
/// translate the user-facing BlurStrength 1..N slider into Kawase
/// parameters. Each entry in ``blurOffsets`` represents a downsample
/// level; ``blurStrengthValues`` is the resulting evenly-distributed
/// slider-position → params mapping.
///
/// The min/max offsets per level come from the upstream Kawase paper:
/// below minOffset the downsample produces blocky artefacts, above
/// maxOffset diagonal line artefacts appear. expandSize is the rim of
/// pixels we have to dirty around the visible region so taps near the
/// edge don't read stale content.
void BlurEffect::initBlurStrengthValues()
{
    // The range of the slider on the blur settings UI.
    int numOfBlurSteps = 20;
    int remainingSteps = numOfBlurSteps;

    // Per-level Kawase tuning — {minOffset, maxOffset, expandSize}.
    // Tuned for the hexagonal disc kernel which covers more area per tap
    // than axis-aligned Kawase — offsets kept low for precise, subtle blur.
    blurOffsets.append({0.5, 1.0, 10}); // Down sample size / 2
    blurOffsets.append({1.0, 1.5, 20}); // Down sample size / 4
    blurOffsets.append({1.0, 2.5, 50}); // Down sample size / 8
    blurOffsets.append({1.5, 4.0, 150}); // Down sample size / 16
    blurOffsets.append({2.5, 5.0, 400}); // Down sample size / 32

    // First pass: compute the total offset range we need to subdivide.
    float offsetSum = 0;
    for (int i = 0; i < blurOffsets.size(); i++) {
        offsetSum += blurOffsets[i].maxOffset - blurOffsets[i].minOffset;
    }

    // Second pass: allocate slider steps proportionally to each level's
    // share of the offset range, then build the final lookup table.
    for (int i = 0; i < blurOffsets.size(); i++) {
        int iterationNumber = std::ceil((blurOffsets[i].maxOffset - blurOffsets[i].minOffset) / offsetSum * numOfBlurSteps);
        remainingSteps -= iterationNumber;

        if (remainingSteps < 0) {
            iterationNumber += remainingSteps;
        }

        float offsetDifference = blurOffsets[i].maxOffset - blurOffsets[i].minOffset;

        for (int j = 1; j <= iterationNumber; j++) {
            // {iteration, offset}
            blurStrengthValues.append({i + 1, blurOffsets[i].minOffset + (offsetDifference / iterationNumber) * j});
        }
    }
}

void BlurEffect::reconfigure(ReconfigureFlags flags)
{
    BlurConfig::self()->read();

    // Fractional blur strength: interpolate offset between neighbouring table entries.
    // Strength 0 = no blur (passthrough).
    double blurStrengthD = qBound(0.0, BlurConfig::blurStrength(), (double) blurStrengthValues.size());

    if (blurStrengthD <= 0.0) {
        m_iterationCount = 1;
        m_offset = 0.0;
        m_expandSize = 0;
    } else {
        // Decode the fractional setting into a (lo, hi, t) lerp triple.
        double idx = blurStrengthD - 1.0; // 0.0 … size-1
        int lo = qBound(0, (int) std::floor(idx), (int) blurStrengthValues.size() - 1);
        int hi = qBound(0, lo + 1, (int) blurStrengthValues.size() - 1);
        float t = (float) (idx - lo);

        // Apply the lerp to the Kawase parameters.
        m_iterationCount = blurStrengthValues[hi].iteration; // enough Kawase passes for the higher level
        m_offset = blurStrengthValues[lo].offset + t * (blurStrengthValues[hi].offset - blurStrengthValues[lo].offset);
        m_expandSize = blurOffsets[m_iterationCount - 1].expandSize;
    }

    // Per-pass tuning knobs.
    m_noiseStrength = BlurConfig::noiseStrength();
    m_colorMatrix = colorTransformMatrix(BlurConfig::saturation(), BlurConfig::contrast(), BlurConfig::brightness());
    m_rgbDriftStrength = static_cast<float>(BlurConfig::rgbDriftStrength());
    m_magnifyGlassStrength = static_cast<float>(BlurConfig::magnifyGlassStrength());
    m_refractionWidth = static_cast<float>(BlurConfig::refractionWidth());
    m_highlightWidth = static_cast<float>(BlurConfig::highlightWidth());
    m_highlightStrength = static_cast<float>(BlurConfig::highlightStrength());
    m_darkGradientOverlay = BlurConfig::darkGradientOverlay();
    const auto gradientColor = [](const QColor &color, double opacity) {
        return QVector4D(color.redF(), color.greenF(), color.blueF(), qBound(0.0, opacity, 1.0));
    };
    const KConfigGroup gradientConfig(BlurConfig::self()->config(), QStringLiteral("Effect-liquidglass"));
    m_gradientTop = gradientColor(BlurConfig::gradientTopColor(), BlurConfig::gradientTopOpacity());
    m_gradientTopDark = gradientColor(gradientConfig.readEntry(QStringLiteral("GradientTopDarkColor"),
        BlurConfig::gradientTopColor()), BlurConfig::gradientTopOpacity());
    m_gradientCenter = gradientColor(BlurConfig::gradientCenterColor(), BlurConfig::gradientCenterOpacity());
    m_gradientCenterDark = gradientColor(gradientConfig.readEntry(QStringLiteral("GradientCenterDarkColor"),
        BlurConfig::gradientCenterColor()), BlurConfig::gradientCenterOpacity());
    m_gradientCenterPosition = qBound(0.0, BlurConfig::gradientCenterPosition(), 1.0);
    m_gradientBottom = gradientColor(BlurConfig::gradientBottomColor(), BlurConfig::gradientBottomOpacity());
    m_gradientBottomDark = gradientColor(gradientConfig.readEntry(QStringLiteral("GradientBottomDarkColor"),
        BlurConfig::gradientBottomColor()), BlurConfig::gradientBottomOpacity());
    m_blurDecorations = BlurConfig::blurDecorations();

    // Window-class filter (whitelist vs blacklist) — the parser below handles
    // the ``$blank`` escape used by the KCM to represent empty entries.
    m_whitelist = BlurConfig::blurMatching();
    m_windowClasses.clear();
    const auto blank = QStringLiteral("blank");
    for (const auto& line : BlurConfig::windowClasses().split("\n", Qt::SkipEmptyParts)) {
        QString unescaped = "";
        bool consumed = false;
        for (qsizetype i = 0; i < line.size(); i++) {
            const auto character = line[i];
            if (character == QChar('$') && !consumed) {
                consumed = true;
                continue;
            }
            if (consumed) {
                const qsizetype skips = blank.size();
                if (line.mid(i, skips) == blank) {
                    consumed = false;
                    i += skips - 1;
                    continue;
                }
            }
            consumed = false;
            unescaped += character;
        }
        if (consumed) {
            unescaped += QChar('$');
        }
        m_windowClasses << unescaped;
    }

    // Re-evaluate the cached blur region of every open window. Without this,
    // a settings change that affects which region is blurred (e.g. toggling
    // BlurDecorations, or editing the window-class match list) would not take
    // effect on already-open windows until each was next moved / resized /
    // re-decorated. addRepaintFull alone only repaints — it reads the stale
    // cached frame/content. Mirrors Better Blur's reconfigure loop.
    for (EffectWindow* w : effects->stackingOrder()) {
        updateBlurRegion(w);
    }

    // Update all windows for the blur to take effect
    effects->addRepaintFull();
}

// Per-window state

/// Recompute the cached blur region + colour matrix for ``w``. Pulls
/// from the X11 property, the Wayland blur/contrast interfaces, the
/// internal QWindow property fallback, and the decoration plugin in
/// that order. Erases the entry entirely when the window has neither
/// content nor frame to blur — the next paint will then fall through
/// to KWin's default opaque path for free.
void BlurEffect::updateBlurRegion(EffectWindow* w)
{
    std::optional<Region> content;
    std::optional<Region> frame;
    std::optional<qreal> saturation;
    std::optional<qreal> contrast;

    // Xwayland still advertises blur through the X11 property on KWin 6.7+,
    // even though EffectWindow::readProperty was removed from that SDK.
#if KWIN_BUILD_X11
    [[maybe_unused]] bool legacyBlurPropertyMissing = false;
    if (net_wm_blur_region != XCB_ATOM_NONE && effects->xcbConnection() && w->windowId()) {
        // Bound the response and reject malformed/truncated properties instead
        // of treating them as the empty "blur the entire window" request.
        const auto cookie = xcb_get_property(effects->xcbConnection(), false,
            xcb_window_t(w->windowId()), net_wm_blur_region, XCB_ATOM_CARDINAL, 0, 16384);
        const std::unique_ptr<xcb_get_property_reply_t, decltype(&std::free)> reply(
            xcb_get_property_reply(effects->xcbConnection(), cookie, nullptr), &std::free);
        legacyBlurPropertyMissing = reply && reply->type == XCB_ATOM_NONE;
        if (reply && reply->type == XCB_ATOM_CARDINAL && reply->format == 32
            && reply->bytes_after == 0 && reply->value_len % 4 == 0) {
            Region region;
            const auto *cardinals = static_cast<const uint32_t *>(xcb_get_property_value(reply.get()));
            for (uint32_t i = 0; i < reply->value_len; i += 4) {
                const int x = int32_t(cardinals[i]);
                const int y = int32_t(cardinals[i + 1]);
                const uint32_t width = cardinals[i + 2];
                const uint32_t height = cardinals[i + 3];
                if (width > INT_MAX || height > INT_MAX
                    || int64_t(x) + width > INT_MAX || int64_t(y) + height > INT_MAX) {
                    region = Region();
                    break;
                }
                region += Xcb::fromXNative(Rect(x, y, int(width), int(height))).toRect();
            }
            // Invalid sizes must not authorize a full-window fallback.
            if (reply->value_len == 0 || !region.isEmpty()) content = region;
        }
    }

#if defined(GLASS_X11)
    // Plasma's translucent menus do not publish the legacy blur-region
    // property on X11. Only synthesize a full-client region for alpha
    // visuals belonging to plasmashell popup windows; opaque menus and
    // application popups keep their existing rendering path.
    if (legacyBlurPropertyMissing && !content.has_value() && effects->xcbConnection() && w->windowId()
        && w->window()->resourceClass() == QStringLiteral("plasmashell")
        && (w->isMenu() || w->isDropdownMenu() || w->isPopupMenu() || w->isAppletPopup())) {
        const auto attributesCookie = xcb_get_window_attributes(
            effects->xcbConnection(), xcb_window_t(w->windowId()));
        const std::unique_ptr<xcb_get_window_attributes_reply_t, decltype(&std::free)> attributes(
            xcb_get_window_attributes_reply(effects->xcbConnection(), attributesCookie, nullptr), &std::free);
        if (attributes && hasAlphaVisual(effects->xcbConnection(), attributes->visual)) {
            content = Region(w->contentsRect().toRect());
        }
    }
#endif
#endif

    // Wayland: prefer the protocol-driven blur/contrast surface state.
    if (SurfaceInterface* surface = w->surface()) {
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
        // 6.7 exposes the blur region directly as a floating-point
        // RegionF (the ext_background_effect_v1 protocol). Convert it to
        // our integer Region rect-by-rect via toAlignedRect(), matching
        // upstream kwin-effects-glass. The contrast/saturation protocol
        // was dropped, so those stay at their defaults (the global colour
        // matrix still applies).
        const RegionF surfaceBlurRegion = surface->blurRegion();
        if (!surfaceBlurRegion.isEmpty()) {
            Region region;
            for (const RectF& rect : surfaceBlurRegion.rects()) {
                region += rect.toAlignedRect();
            }
            content = region;
        }
#else
        if (surface->blur()) {
            content = surface->blur()->region();
        }
        if (surface->contrast()) {
            saturation = surface->contrast()->saturation();
            contrast = surface->contrast()->contrast();
        }
#endif
    }

    // Internal QWindow fallback: Plasma's internal windows attach a
    // ``kwin_blur`` dynamic property carrying the desired region.
    if (auto internal = w->internalWindow()) {
        const auto property = internal->property("kwin_blur");
        if (property.isValid()) {
            content = property.value<Region>();
        }
    }

    // GTK does not publish a blur protocol region. Keep its client blur
    // independent of the server-side decoration setting.
    const auto isNautilus = [](const QString &name) {
        return name.compare(QStringLiteral("org.gnome.Nautilus"), Qt::CaseInsensitive) == 0
            || name.compare(QStringLiteral("nautilus"), Qt::CaseInsensitive) == 0;
    };
    if (!content.has_value() && w->isNormalWindow()
        && (isNautilus(w->window()->resourceClass()) || isNautilus(w->window()->resourceName()))) {
        // An empty request means the entire client, without applying the
        // server-decoration content offset twice. It also avoids the
        // ambiguous QRect -> Region conversion in KWin 6.6.
        content = Region();
    }

    // Decoration-side blur: opt-in via the KDecoration3 protocol, else
    // implicit for normal windows (skip docks / menus / popups so their
    // own opaque chrome doesn't double-blur).
    if (m_blurDecorations && w->decorationHasAlpha() && decorationSupportsBlurBehind(w)) {
        frame = decorationBlurRegion(w);
    } else if (m_blurDecorations && !(w->isDock() || w->isTooltip() || w->isMenu() || w->isDropdownMenu() || w->isPopupMenu() || w->isPopupWindow() || w->isAppletPopup())) {
        frame = Rect(w->frameGeometry().translated(-w->x(), -w->y()).toRect());
    }

    // Commit (or evict).
    if (content.has_value() || frame.has_value()) {
        BlurEffectData& data = m_windows[w];
        data.content = content;
        data.frame = frame;
        data.clientShape.reset();
        if (!w->decoration() && content.has_value() && !frame.has_value()
            && (w->isDock() || w->isTooltip() || w->isMenu() || w->isDropdownMenu()
                || w->isPopupMenu() || w->isAppletPopup() || w->isPopupWindow())) {
            QRegion clientRegion;
            for (const Rect &rect : content->rects()) {
                clientRegion += QRect(rect);
            }
            data.clientShape = clientBlurShape(clientRegion & w->contentsRect().toRect());
        }
        data.colorMatrix = colorTransformMatrix(saturation.value_or(1.0), contrast.value_or(1.0), 1.0);
        data.windowEffect = ItemEffect(w->windowItem());
#if ACRYLIC_GLASS_SCENE_DAMAGE
        // KWin collects damage after prePaintWindow. Register the sampling
        // bounds in its scene so partial backdrop updates repaint the blur.
        if (!data.backgroundEffect) {
            data.backgroundEffect = std::make_unique<BackgroundEffectItem>(w->windowItem());
        }
        data.backgroundEffect->setEffectBoundingRect(RectF(blurRegion(w).boundingRect()));
        data.backgroundEffect->setPixelsToExpandRepaintsBelowOpaqueRegions(w->isDock() ? 50 : m_expandSize);
#endif
    } else {
        if (auto it = m_windows.find(w); it != m_windows.end()) {
            effects->makeOpenGLContextCurrent();
            m_windows.erase(it);
        }
    }
}

/// Wire signal forwarding so any later change to ``w``'s surface,
/// frame geometry, or decoration triggers an updateBlurRegion call.
/// Also runs an initial update so the cache is primed before the first
/// paint.
void BlurEffect::slotWindowAdded(EffectWindow* w)
{
    SurfaceInterface* surf = w->surface();

    if (surf) {
        windowBlurChangedConnections[w] = connect(surf, &SurfaceInterface::blurChanged, this, [this, w]() {
            if (w) {
                updateBlurRegion(w);
            }
        });

#if !ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
        // contrastChanged was removed with the 6.7 protocol merge.
        windowContrastChangedConnections[w] = connect(surf, &SurfaceInterface::contrastChanged, this, [this, w]() {
            if (w) {
                updateBlurRegion(w);
            }
        });
#endif
    }

    windowFrameGeometryChangedConnections[w] = connect(w, &EffectWindow::windowFrameGeometryChanged, this, [this, w]() {
        if (w) {
            updateBlurRegion(w);
        }
    });

    if (auto internal = w->internalWindow()) {
        internal->installEventFilter(this);
    }

    setupDecorationConnections(w);
    connect(w, &EffectWindow::windowDecorationChanged, this, [this, w]() {
        setupDecorationConnections(w);
        updateBlurRegion(w);
    });

    if (!windowWobblyConnections.contains(w)) {
        WobblyConnections connections;
        connections.start = connect(w, &EffectWindow::windowStartUserMovedResized, this,
            [this](EffectWindow* window) { slotWindowStartUserMovedResized(window); });
        connections.step = connect(w, &EffectWindow::windowStepUserMovedResized, this,
            [this](EffectWindow* window, const auto&) { slotWindowStepUserMovedResized(window); });
        connections.finish = connect(w, &EffectWindow::windowFinishUserMovedResized, this,
            [this](EffectWindow* window) { slotWindowFinishUserMovedResized(window); });
        windowWobblyConnections.insert(w, connections);
    }

    updateBlurRegion(w);
}

/// Tear down all per-window state. Each connection is looked up and
/// disconnected individually — the QMap stays consistent even if some
/// of the signals were never wired in the first place.
void BlurEffect::slotWindowDeleted(EffectWindow* w)
{
    if (auto it = m_windows.find(w); it != m_windows.end()) {
        effects->makeOpenGLContextCurrent();
        m_windows.erase(it);
    }
    wobblyShapes.erase(w);

    if (auto it = windowBlurChangedConnections.find(w); it != windowBlurChangedConnections.end()) {
        disconnect(*it);
        windowBlurChangedConnections.erase(it);
    }

#if !ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
    if (auto it = windowContrastChangedConnections.find(w); it != windowContrastChangedConnections.end()) {
        disconnect(*it);
        windowContrastChangedConnections.erase(it);
    }
#endif

    if (auto it = windowFrameGeometryChangedConnections.find(w); it != windowFrameGeometryChangedConnections.end()) {
        disconnect(*it);
        windowFrameGeometryChangedConnections.erase(it);
    }

    if (auto it = windowWobblyConnections.find(w); it != windowWobblyConnections.end()) {
        disconnect(it->start);
        disconnect(it->step);
        disconnect(it->finish);
        windowWobblyConnections.erase(it);
    }
}

/// Drop the per-view scratch buffers (textures + framebuffers) for an
/// output that just disappeared. Each window's render map is keyed by
/// RenderView*, so we walk every window once.
#if !defined(GLASS_X11)
void BlurEffect::slotViewRemoved(KWin::RenderView* view)
{
    for (auto& [window, data] : m_windows) {
        if (auto it = data.render.find(view); it != data.render.end()) {
            effects->makeOpenGLContextCurrent();
            data.render.erase(it);
        }
    }
}
#endif

#if KWIN_BUILD_X11
/// X11 only: re-read the blur-behind property when the client updates
/// it. Filters out unrelated atoms cheaply before doing any work.
void BlurEffect::slotPropertyNotify(EffectWindow* w, long atom)
{
    if (w && atom == net_wm_blur_region && net_wm_blur_region != XCB_ATOM_NONE) {
        updateBlurRegion(w);
    }
}
#endif

/// Subscribe to ``blurRegionChanged`` on the window's decoration so
/// titlebar/edge blur stays in sync. No-op for undecorated windows.
void BlurEffect::setupDecorationConnections(EffectWindow* w)
{
    if (!w->decoration()) {
        return;
    }

    connect(w->decoration(), &KDecoration3::Decoration::blurRegionChanged, this, [this, w]() { updateBlurRegion(w); });
}

std::optional<WobblyShapeParameters> BlurEffect::readWobblyParameters(bool resizing) const
{
    Effect* wobbly = effects->findEffect(QStringLiteral("wobblywindows"));
    if (!wobbly) {
        return std::nullopt;
    }

    if (!wobbly->property(resizing ? "resizeWobble" : "moveWobble").toBool()) {
        return std::nullopt;
    }

    WobblyShapeParameters parameters;
    parameters.stiffness = wobbly->property("stiffness").toReal();
    parameters.drag = wobbly->property("drag").toReal();
    parameters.moveFactor = wobbly->property("moveFactor").toReal();
    parameters.minVelocity = wobbly->property("minVelocity").toReal();
    parameters.maxVelocity = wobbly->property("maxVelocity").toReal();
    parameters.stopVelocity = wobbly->property("stopVelocity").toReal();
    parameters.minAcceleration = wobbly->property("minAcceleration").toReal();
    parameters.maxAcceleration = wobbly->property("maxAcceleration").toReal();
    parameters.stopAcceleration = wobbly->property("stopAcceleration").toReal();
    // KWin X11 and older Wayland SDKs retain the original single-s
    // property spelling. A missing property converts to zero and would
    // silently disable our mesh for every drag on those backends.
    const QVariant xTessellation = wobbly->property("xTessellation");
    const QVariant yTessellation = wobbly->property("yTessellation");
    parameters.xTessellation = xTessellation.isValid()
        ? xTessellation.toInt() : wobbly->property("xTesselation").toInt();
    parameters.yTessellation = yTessellation.isValid()
        ? yTessellation.toInt() : wobbly->property("yTesselation").toInt();

    if (parameters.xTessellation <= 0 || parameters.yTessellation <= 0) {
        return std::nullopt;
    }
    return parameters;
}

void BlurEffect::slotWindowStartUserMovedResized(EffectWindow* w)
{
    if (!w || w->isSpecialWindow()) {
        return;
    }

    const bool resizing = w->isUserResize();
    if (!w->isUserMove() && !resizing) {
        return;
    }

    const std::optional<WobblyShapeParameters> parameters = readWobblyParameters(resizing);
    if (!parameters) {
        return;
    }

    const QPointF cursorPosition = Effect::cursorPos();
    const QRectF geometry = w->frameGeometry();
    auto it = wobblyShapes.find(w);
    if (it != wobblyShapes.end() && !it->second.retirePending()) {
        // Wobbly keeps its spring model and clock when a drag is released
        // and restarted before the previous motion has settled.
        it->second.beginMovedResized(cursorPosition, geometry, resizing);
    } else {
        if (it != wobblyShapes.end()) {
            wobblyShapes.erase(it);
        }
        wobblyShapes.try_emplace(w, *parameters, geometry, cursorPosition, resizing);
    }
}

void BlurEffect::slotWindowStepUserMovedResized(EffectWindow* w)
{
    if (auto it = wobblyShapes.find(w); it != wobblyShapes.end()) {
        it->second.shape().noteGeometryStep(w->frameGeometry());
    }
}

void BlurEffect::slotWindowFinishUserMovedResized(EffectWindow* w)
{
    if (auto it = wobblyShapes.find(w); it != wobblyShapes.end()) {
        it->second.shape().noteGeometryFinished(w->frameGeometry());
    }
}

void BlurEffect::advanceWobblyShape(RenderView* view, EffectWindow* w ACRYLIC_GLASS_PRESENT_TIME_PARAM)
{
    auto it = wobblyShapes.find(w);
    if (it == wobblyShapes.end()) {
        return;
    }

#if ACRYLIC_GLASS_KWIN_6_7
    const bool active = it->second.advance(view, w->frameGeometry());
#else
    const bool active = it->second.advance(presentTime, w->frameGeometry());
#endif
    if (!active) {
        wobblyShapes.erase(it);
    }
}

/// Catch ``kwin_blur`` dynamic property changes on internal QWindows
/// (Plasma's own popups use this path instead of the Wayland blur
/// interface). Returns ``false`` so other event filters still see the
/// event.
bool BlurEffect::eventFilter(QObject* watched, QEvent* event)
{
    auto internal = qobject_cast<QWindow*>(watched);

    if (internal && event->type() == QEvent::DynamicPropertyChange) {
        QDynamicPropertyChangeEvent* pe = static_cast<QDynamicPropertyChangeEvent*>(event);

        if (pe->propertyName() == "kwin_blur") {
            if (auto w = effects->findWindow(internal)) {
                updateBlurRegion(w);
            }
        }
    }

    return false;
}

// Feature gates

/// We opt out of auto-enable so the installer's kwinrc patch is the single
/// source of truth — see ``steps/acrylic_glass.py``.
bool BlurEffect::enabledByDefault()
{
    return false;
}

/// Cheapest possible support check — anything beyond OpenGL compositing
/// would require allocating GL resources, which we'd rather defer to the
/// constructor.
bool BlurEffect::supported()
{
    return effects->isOpenGLCompositing();
}

// Region helpers

/// True iff the active KDecoration opts into the blur-behind protocol by
/// declaring a non-null blur region.
bool BlurEffect::decorationSupportsBlurBehind(const EffectWindow* w) const
{
    return w->decoration() && !w->decoration()->blurRegion().isNull();
}

/// Restrict the decoration's declared blur region to the actual frame
/// (everything outside the client content rect). Stops the content area
/// from being double-blurred when the decoration claims a region that
/// overlaps it.
Region BlurEffect::decorationBlurRegion(const EffectWindow* w) const
{
    if (!decorationSupportsBlurBehind(w)) {
        return Region();
    }

    Region decorationRegion = Region(Rect(w->decoration()->rect().toAlignedRect())) - w->contentsRect().toRect();
    return decorationRegion.intersected(Region(w->decoration()->blurRegion()));
}

/// Compose the effective blur region from the cached per-window content
/// + frame masks. An empty ``content`` is special-cased to mean "blur
/// the whole window content rect" (Wayland blur protocol semantics).
Region BlurEffect::blurRegion(EffectWindow* w) const
{
    Region region;

    if (auto it = m_windows.find(w); it != m_windows.end()) {
        const std::optional<Region>& content = it->second.content;
        const std::optional<Region>& frame = it->second.frame;
        const bool clientPopup = !w->decoration() && (w->isDock() || w->isTooltip()
            || w->isMenu() || w->isDropdownMenu() || w->isPopupMenu()
            || w->isAppletPopup() || w->isPopupWindow());

        if (content.has_value()) {
            if (content->isEmpty()) {
                // Empty optional → "blur everything inside the content rect".
                region = Rect(w->contentsRect().toRect());
            } else if (w->decoration()) {
                region = content->translated(w->contentsRect().topLeft().toPoint()) & w->contentsRect().toRect();
            } else {
                region = *content & w->contentsRect().toRect();
            }

            if (frame.has_value() && !clientPopup) {
                region += frame.value();
            }
        } else if (frame.has_value() && !clientPopup) {
            region = frame.value();
        }
    }

    return region;
}

// Per-frame entry points

/// Reset per-frame accumulators and remember which view we're painting
/// so prePaintWindow / blur can attribute their dirty regions correctly.
void BlurEffect::prePaintScreen(ScreenPrePaintData& data ACRYLIC_GLASS_PRESENT_TIME_PARAM)
{
    m_paintedDeviceArea = Region();
    m_currentDeviceBlur = Region();
#if defined(GLASS_X11)
    m_currentView = nullptr;
#else
    m_currentView = data.view;
#endif

    effects->prePaintScreen(data ACRYLIC_GLASS_PRESENT_TIME_ARG);
}

/// Expand the dirty / opaque regions so the Kawase chain has the
/// surrounding pixels it needs to sample, and so KWin doesn't occlude
/// (= skip) the background behind our blur area as a perf optimisation.
#if defined(GLASS_X11)
void BlurEffect::prePaintWindow(EffectWindow* w, WindowPrePaintData& data ACRYLIC_GLASS_PRESENT_TIME_PARAM)
#else
void BlurEffect::prePaintWindow(RenderView* view, EffectWindow* w, WindowPrePaintData& data ACRYLIC_GLASS_PRESENT_TIME_PARAM)
#endif
{
#if defined(GLASS_X11)
    m_currentView = w->screen();
#endif
    // The Plasma shell role may arrive after the first blur region. KWin
    // exposes no window-type change signal; discard an earlier implicit
    // rectangular frame as soon as the window becomes an applet popup.
    if (!w->decoration() && (w->isDock() || w->isTooltip() || w->isMenu()
        || w->isDropdownMenu() || w->isPopupMenu() || w->isAppletPopup() || w->isPopupWindow())) {
        const auto it = m_windows.find(w);
        if (it != m_windows.end() && it->second.frame.has_value()) {
            updateBlurRegion(w);
        }
    }
#if defined(GLASS_X11)
    effects->prePaintWindow(w, data ACRYLIC_GLASS_PRESENT_TIME_ARG);
    advanceWobblyShape(m_currentView, w ACRYLIC_GLASS_PRESENT_TIME_ARG);
#else
    effects->prePaintWindow(view, w, data ACRYLIC_GLASS_PRESENT_TIME_ARG);
    advanceWobblyShape(view, w ACRYLIC_GLASS_PRESENT_TIME_ARG);
#endif

#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
    // On KWin 6.7+ the ext_background_effect_v1 machinery owns the
    // dirty/opaque bookkeeping, so no manual pass is needed. The
    // WindowPrePaintData::deviceOpaque / devicePaint members it poked are
    // gone; the effect just marks the window translucent so KWin paints
    // the background we sample. Matches upstream kwin-effects-glass.
#if !defined(GLASS_X11)
    Q_UNUSED(view)
#endif
    if (!blurRegion(w).isEmpty()) {
        data.setTranslucent();
    }
#else
    // 1. The visible blur area for this window, mapped to device px.
#if defined(GLASS_X11)
    const Region blurArea = QRectF(blurRegion(w).boundingRect()).translated(w->pos()).toAlignedRect();
#else
    const Region blurArea = view->mapToDeviceCoordinatesAligned(QRectF(blurRegion(w).boundingRect()).translated(w->pos()));
#endif

    if (!blurArea.isEmpty()) {
        // 2. FORCE TRANSPARENCY: Remove the blur area from the opaque
        // region. Otherwise KWin "occludes" (= skips) the rendering of
        // whatever sits behind us, and our blur reads stale pixels.
#if defined(GLASS_X11)
        data.opaque -= blurArea;
#else
        data.deviceOpaque -= blurArea;
#endif

        // 3. EXPAND PAINT REGION: Pull in pixels from slightly outside
        // the visible bounds so refraction / Kawase taps near the rim
        // sample real content, not whatever was left in the buffer.
        Region expandedBlur = blurArea;
        const int expandSize = w->isDock() ? 50 : m_expandSize;
        for (const Rect& rect : blurArea.rects()) {
            expandedBlur += rect.adjusted(-expandSize, -expandSize, expandSize, expandSize);
        }

        // Ensure the compositor actually paints the background we need to sample.
#if defined(GLASS_X11)
        data.paint += (expandedBlur - data.opaque);
#else
        data.devicePaint += (expandedBlur - data.deviceOpaque);
#endif
    }

    // Carry over the blur "damage" to windows lower in the stack so they
    // also repaint — otherwise a moving window behind a stationary glass
    // surface leaves trails.
#if defined(GLASS_X11)
    if (m_paintedDeviceArea.intersects(blurArea) || data.paint.intersects(blurArea)) {
        data.paint += blurArea;
    }
    m_currentDeviceBlur += blurArea;
    m_paintedDeviceArea -= data.opaque;
    m_paintedDeviceArea += data.paint;
#else
    if (m_paintedDeviceArea.intersects(blurArea) || data.devicePaint.intersects(blurArea)) {
        data.devicePaint += blurArea;
    }

    m_currentDeviceBlur += blurArea;
    m_paintedDeviceArea -= data.deviceOpaque;
    m_paintedDeviceArea += data.devicePaint;
#endif
#endif
}

/// Master gate: every disqualifying condition (fullscreen effect active,
/// desktop window, the xwaylandvideobridge screen-share helper, Spectacle's
/// capture overlay, class-filter mismatch, transformed window) short-
/// circuits to ``false``. ``WindowForceBlurRole`` is the per-window
/// override Plasma uses to opt specific windows in regardless.
bool BlurEffect::shouldBlur(const EffectWindow* w, int mask, const WindowPaintData& data) const
{
    if (effects->activeFullScreenEffect() && !w->data(WindowForceBlurRole).toBool()) {
        return false;
    }

    if (w->isDesktop()) {
        return false;
    }

    // Class / resource filter — whitelist OR blacklist depending on the
    // BlurMatching kcfg toggle.
    const auto windowClass = w->window()->resourceClass();
    const auto resourceName = w->window()->resourceName();

    // VirtualBox's VM surface carries the guest's fullscreen/seamless
    // content and transparent cutouts. Painting forced glass behind it
    // fills those cutouts with a desktop-sized sheet (issue #90). Keep
    // this outside the configurable match modes so existing installs
    // and custom lists are protected too. The VirtualBox manager has a
    // different class and keeps its normal appearance.
    if (windowClass.compare(QStringLiteral("VirtualBoxVM"), Qt::CaseInsensitive) == 0
        || resourceName.compare(QStringLiteral("VirtualBoxVM"), Qt::CaseInsensitive) == 0) {
        return false;
    }

    // xwaylandvideobridge is the helper that bridges Wayland windows into
    // XWayland for screen sharing (Discord / OBS / browser capture). It
    // maps an invisible, screen-sized surface that must never be blurred —
    // otherwise it paints a fullscreen glass sheet over the whole desktop.
    // This is an unconditional skip placed before the whitelist/blacklist
    // branch so it holds in either matching mode (a default config entry
    // would invert to "only blur the bridge" under whitelist mode). Matches
    // the hardcoded exclusion in upstream KWin / Better Blur — case-
    // sensitive against the lowercase resourceClass KWin reports.
    if (windowClass == QStringLiteral("xwaylandvideobridge")) {
        return false;
    }

    // Spectacle's full-screen capture / rectangular-region overlay must
    // never be blurred — otherwise the selector frosts the frozen desktop
    // and the glass can bake into the saved screenshot. Gate on the
    // overlay / active layer so Spectacle's ordinary settings window (in
    // the normal layer) still blurs. Same unconditional placement as the
    // bridge skip; mirrors the hardcoded exclusion in upstream Better Blur.
    const auto layer = w->window()->layer();
    if ((windowClass == QStringLiteral("spectacle") || windowClass == QStringLiteral("org.kde.spectacle"))
        && (layer == OverlayLayer || layer == ActiveLayer)) {
        return false;
    }
    const auto matches = m_windowClasses.contains(windowClass) || m_windowClasses.contains(resourceName);

    if ((m_whitelist && !matches) || (!m_whitelist && matches)) {
        return false;
    }

    // Skip transformed windows unless Wobbly Windows is driving this
    // particular window. Wobbly keeps WindowPaintData at 1x/identity and
    // supplies geometry through its own WindowQuadList, but still sets
    // PAINT_WINDOW_TRANSFORMED. Dropping the glass for that flag caused
    // the start/end drag flash. Overview, present-windows and other
    // transforms remain excluded.
    bool scaled = !qFuzzyCompare(data.xScale(), 1.0) || !qFuzzyCompare(data.yScale(), 1.0);
    bool translated = data.xTranslation() || data.yTranslation();
    const bool wobblyTransformed = (mask & PAINT_WINDOW_TRANSFORMED)
        && std::any_of(wobblyShapes.cbegin(), wobblyShapes.cend(), [w](const auto& entry) { return entry.first == w; });

    if ((scaled || translated) && !w->data(WindowForceBlurRole).toBool()) {
        return false;
    }

    if ((mask & PAINT_WINDOW_TRANSFORMED) && !wobblyTransformed && !w->data(WindowForceBlurRole).toBool()) {
        return false;
    }

    return true;
}

/// Delegate to ``blur()`` (which handles its own shouldBlur gate
/// internally), then defer to KWin's default to draw the actual window
/// content on top of the blurred background.
AcrylicGlassDrawWindowResult BlurEffect::drawWindow(
    const RenderTarget& renderTarget, const RenderViewport& viewport, EffectWindow* w, int mask, const Region& deviceRegion, WindowPaintData& data)
{
    blur(renderTarget, viewport, w, mask, deviceRegion, data);

#if ACRYLIC_GLASS_KWIN_6_8
    return effects->drawWindow(renderTarget, viewport, w, mask, deviceRegion, data);
#else
    effects->drawWindow(renderTarget, viewport, w, mask, deviceRegion, data);
#endif
}

// Noise grain texture

/// Lazily build (and cache) a 256×256 grayscale noise texture for the
/// grain pass. Rebuilds when DPI scale or strength changes. Returns
/// nullptr when noise is disabled (strength 0) — callers skip the
/// whole noise pass in that case.
GLTexture* BlurEffect::ensureNoiseTexture()
{
    if (m_noiseStrength == 0) {
        return nullptr;
    }

    const qreal scale = std::max(1.0, QGuiApplication::primaryScreen()->logicalDotsPerInch() / 96.0);

    if (!m_noisePass.noiseTexture || m_noisePass.noiseTextureScale != scale || m_noisePass.noiseTextureStength != m_noiseStrength) {
        // Seed from the clock so consecutive frames don't all use the
        // same pattern (subtle temporal jitter).
        std::srand((uint) QTime::currentTime().msec());

        QImage noiseImage(QSize(256, 256), QImage::Format_Grayscale8);
        for (int y = 0; y < noiseImage.height(); y++) {
            uint8_t* noiseImageLine = (uint8_t*) noiseImage.scanLine(y);
            for (int x = 0; x < noiseImage.width(); x++) {
                noiseImageLine[x] = std::rand() % m_noiseStrength;
            }
        }

        noiseImage = noiseImage.scaled(noiseImage.size() * scale);

        m_noisePass.noiseTexture = GLTexture::upload(noiseImage);
        if (!m_noisePass.noiseTexture) {
            return nullptr;
        }

        m_noisePass.noiseTexture->setFilter(GL_NEAREST);
        m_noisePass.noiseTexture->setWrapMode(GL_REPEAT);
        m_noisePass.noiseTextureScale = scale;
        m_noisePass.noiseTextureStength = m_noiseStrength;
    }

    return m_noisePass.noiseTexture.get();
}

// Main blur pipeline

/// The whole show. Walked by drawWindow() for every blurred window in
/// the current frame. Phases (each preceded by a ``// <name>`` section
/// header below):
///
///   1. Bail-out gates (no cached data, shouldBlur says no).
///   2. Compute the effective blur shape, applying any window transform.
///   3. Reallocate per-view framebuffers if size / format changed.
///   4. Blit the background into framebuffers[0].
///   5. Upload the offscreen + onscreen vertex geometry.
///   6. Run the Kawase downsample / upsample loop (skipped at offset 0).
///   7. Resolve the per-window corner radius (window vs dock vs popup).
///   8. Configure + draw the onscreen pass — SDF, drift, lens, rim.
///   9. Optional grain pass on top of the blurred result.
void BlurEffect::blur(
    const RenderTarget& renderTarget, const RenderViewport& viewport, EffectWindow* w, int mask, const Region& deviceRegion, WindowPaintData& data)
{
    // 1. Bail-out gates
    auto it = m_windows.find(w);
    if (it == m_windows.end()) {
        return;
    }

    BlurEffectData& blurInfo = it->second;
    BlurRenderData& renderInfo = blurInfo.render[m_currentView];

    if (!shouldBlur(w, mask, data)) {
        return;
    }

    // A single downsample with widely spaced finish taps splits backdrop
    // edges into copies. Reconstruct a compact pyramid instead, and avoid
    // leaking a sharp image through the centre of the blurred material.
    const bool dockSurface = w->isDock();
    const auto optics = opticsForSurface(dockSurface, {m_rgbDriftStrength, m_magnifyGlassStrength,
        m_refractionWidth, m_highlightWidth, m_highlightStrength});
    const float centerOpacity = dockSurface ? 0.98f : 1.0f;
    // Freeze Dock optics at the v0.62.0 material (BlurStrength 5), including
    // repaint expansion above. Window presets and fine tuning must not leak in.
    const size_t iterationCount = dockSurface ? size_t(3) : m_iterationCount;
    const float blurOffset = dockSurface ? 5.0f * 0.14f : m_offset;

    // 2. Effective blur shape
    // Wobbly supplies its deformation through WindowQuadList rather than
    // WindowPaintData. Mirror its cubic surface here and expand the
    // background capture to the real, non-linear silhouette.
    const auto wobblyIt = wobblyShapes.find(w);
    const bool wobblySurface = wobblyIt != wobblyShapes.end();
    const QRectF frameRect = w->frameGeometry();

    Region blurShape = blurRegion(w).translated(w->pos().toPoint());
    if (!wobblySurface) {
        if (data.xScale() != 1 || data.yScale() != 1) {
            QPoint pt = blurShape.boundingRect().topLeft();
            Region scaledShape;

            for (const Rect& r : blurShape.rects()) {
                const QPointF topLeft(
                    pt.x() + (r.x() - pt.x()) * data.xScale() + data.xTranslation(), pt.y() + (r.y() - pt.y()) * data.yScale() + data.yTranslation());
                const QPoint bottomRight(std::floor(topLeft.x() + r.width() * data.xScale()) - 1, std::floor(topLeft.y() + r.height() * data.yScale()) - 1);
                scaledShape += QRect(QPoint(std::floor(topLeft.x()), std::floor(topLeft.y())), bottomRight);
            }

            blurShape = scaledShape;
        } else if (data.xTranslation() || data.yTranslation()) {
            blurShape.translate(std::round(data.xTranslation()), std::round(data.yTranslation()));
        }
    }

    QRect backgroundRect;
    if (wobblySurface) {
        const QRectF mappedBounds = wobblyIt->second.shape().mappedBounds(frameRect);
        const QPointF frameOrigin(w->x(), w->y());
        const QPointF transformedTopLeft(
            frameOrigin.x() + (mappedBounds.left() - frameOrigin.x()) * data.xScale() + data.xTranslation(),
            frameOrigin.y() + (mappedBounds.top() - frameOrigin.y()) * data.yScale() + data.yTranslation());
        const QPointF transformedBottomRight(
            frameOrigin.x() + (mappedBounds.right() - frameOrigin.x()) * data.xScale() + data.xTranslation(),
            frameOrigin.y() + (mappedBounds.bottom() - frameOrigin.y()) * data.yScale() + data.yTranslation());
        backgroundRect = QRectF(transformedTopLeft, transformedBottomRight)
                            .adjusted(-2.0, -2.0, 2.0, 2.0)
                            .toAlignedRect();
    } else {
        backgroundRect = blurShape.boundingRect();
    }

    if (backgroundRect.isEmpty()) {
        return;
    }

#if defined(GLASS_X11)
    const QRect deviceBackgroundRect = agSnapToPixelGrid(viewport.mapToRenderTarget(backgroundRect));
    const QRect scaledBackgroundRect(QPoint(0, 0), deviceBackgroundRect.size());
#else
    const QRect scaledBackgroundRect = agSnapToPixelGrid(scaledRect(backgroundRect, viewport.scale()));
    const QRect deviceBackgroundRect = agSnapToPixelGrid(viewport.mapToDeviceCoordinates(backgroundRect));
#endif
    const auto opacity = data.opacity();

    // Intersect the shape with the deviceRegion clip — empty after the
    // intersection means everything is clipped and there's nothing to draw.
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
    const bool finiteClip = deviceRegion != Region::infinite();
#else
    const bool finiteClip = true;
#endif
    QList<RectF> effectiveShape;
    if (!wobblySurface) {
        effectiveShape.reserve(blurShape.rects().size());
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
        if (deviceRegion != Region::infinite()) {
#else
        {
#endif
            for (const Rect& clipRect : deviceRegion.rects()) {
                const RectF deviceClipRect = clipRect.translated(-deviceBackgroundRect.topLeft());
                for (const Rect& shapeRect : blurShape.rects()) {
#if defined(GLASS_X11)
                    const RectF deviceShapeRect = viewport.mapToRenderTarget(shapeRect)
                        .translated(-deviceBackgroundRect.topLeft());
#else
                    const RectF deviceShapeRect = shapeRect.translated(-backgroundRect.topLeft()).scaled(viewport.scale()).rounded();
#endif
                    if (const QRectF intersected = deviceClipRect.intersected(deviceShapeRect); !intersected.isEmpty()) {
                        effectiveShape.append(intersected);
                    }
                }
            }
#if ACRYLIC_GLASS_WAYLAND_BACKGROUND_EFFECT_V1
        } else {
            for (const Rect& rect : blurShape.rects()) {
#if defined(GLASS_X11)
                effectiveShape.append(viewport.mapToRenderTarget(rect).translated(-deviceBackgroundRect.topLeft()));
#else
                effectiveShape.append(rect.translated(-backgroundRect.topLeft()).scaled(viewport.scale()).rounded());
#endif
            }
        }
#else
        }
#endif
        if (effectiveShape.isEmpty()) {
            return;
        }
    } else if (finiteClip && (deviceRegion & deviceBackgroundRect).isEmpty()) {
        return;
    }

    std::vector<GLVertex2D> wobblyVertices;
    if (wobblySurface) {
        const WobblyShape& shape = wobblyIt->second.shape();
        const int xTessellation = shape.xTessellation();
        const int yTessellation = shape.yTessellation();
        std::vector<QRectF> clipRects;
        if (finiteClip) {
            const QRectF surfaceBounds(0.0, 0.0, scaledBackgroundRect.width(), scaledBackgroundRect.height());
            clipRects.reserve(deviceRegion.rects().size());
            for (const Rect& clipRect : deviceRegion.rects()) {
                const QRectF localClip(
                    clipRect.x() - deviceBackgroundRect.x(),
                    clipRect.y() - deviceBackgroundRect.y(),
                    clipRect.width(),
                    clipRect.height());
                if (const QRectF intersected = localClip.intersected(surfaceBounds); !intersected.isEmpty()) {
                    clipRects.push_back(intersected);
                }
            }
            if (clipRects.empty()) {
                return;
            }
        }
        wobblyVertices.reserve(static_cast<size_t>(xTessellation) * yTessellation * 6 * std::max<size_t>(1, clipRects.size()));

        const QPointF frameOrigin(w->x(), w->y());
#if !defined(GLASS_X11)
        const QPointF deviceBackgroundOrigin(scaledBackgroundRect.x(), scaledBackgroundRect.y());
#endif
        const auto toDeviceLocal = [&](const QPointF& globalPoint) {
            const QPointF transformed(
                frameOrigin.x() + (globalPoint.x() - frameOrigin.x()) * data.xScale() + data.xTranslation(),
                frameOrigin.y() + (globalPoint.y() - frameOrigin.y()) * data.yScale() + data.yTranslation());
#if defined(GLASS_X11)
            return QVector2D(viewport.mapToRenderTarget(transformed) - QPointF(deviceBackgroundRect.topLeft()));
#else
            return QVector2D(
                static_cast<float>(transformed.x() * viewport.scale() - deviceBackgroundOrigin.x()),
                static_cast<float>(transformed.y() * viewport.scale() - deviceBackgroundOrigin.y()));
#endif
        };

        const auto makeVertex = [&](qreal u, qreal v) {
            const QPointF sourcePoint(frameRect.x() + u * frameRect.width(), frameRect.y() + v * frameRect.height());
            return GLVertex2D{
                .position = toDeviceLocal(shape.map(u, v, frameRect)),
                .texcoord = toDeviceLocal(sourcePoint),
            };
        };

        for (int row = 0; row < yTessellation; ++row) {
            const qreal v0 = static_cast<qreal>(row) / yTessellation;
            const qreal v1 = static_cast<qreal>(row + 1) / yTessellation;
            for (int column = 0; column < xTessellation; ++column) {
                const qreal u0 = static_cast<qreal>(column) / xTessellation;
                const qreal u1 = static_cast<qreal>(column + 1) / xTessellation;

                // Preserve the client's blur region while deforming it. A
                // full-frame mesh would blur deliberately transparent holes.
                const QRectF cell(frameRect.x() + u0 * frameRect.width(),
                    frameRect.y() + v0 * frameRect.height(),
                    (u1 - u0) * frameRect.width(), (v1 - v0) * frameRect.height());
                for (const Rect& regionRect : blurShape.rects()) {
                    const QRectF part = cell.intersected(QRectF(regionRect));
                    if (part.isEmpty()) {
                        continue;
                    }
                    const qreal left = (part.left() - frameRect.x()) / frameRect.width();
                    const qreal right = (part.right() - frameRect.x()) / frameRect.width();
                    const qreal top = (part.top() - frameRect.y()) / frameRect.height();
                    const qreal bottom = (part.bottom() - frameRect.y()) / frameRect.height();
                    appendClippedTriangle(wobblyVertices,
                        {makeVertex(left, top), makeVertex(right, bottom), makeVertex(left, bottom)}, clipRects);
                    appendClippedTriangle(wobblyVertices,
                        {makeVertex(left, top), makeVertex(right, top), makeVertex(right, bottom)}, clipRects);
                }
            }
        }
        if (wobblyVertices.empty()) {
            return;
        }
    }

    // 3. Framebuffer (re)allocation
    // textures[0] holds the un-blurred capture. textures[1..N] are the
    // Kawase chain. We reallocate when the iteration count, size, or
    // texture format changed — KWin gives us the render target's own
    // format so HDR / 10-bit pipelines work without quantising to RGBA8.
    GLenum textureFormat = GL_RGBA8;
    if (renderTarget.texture()) {
        textureFormat = renderTarget.texture()->internalFormat();
    }

    // Allocate framebuffers in DEVICE pixels (scaledBackgroundRect), not
    // logical pixels (backgroundRect). KWin's render target is at the
    // active output scale (viewport.scale(), e.g. 1.5× on this HiDPI
    // setup), so allocating at logical size makes blitFromRenderTarget
    // silently resample the background DOWN to logical resolution
    // before any shader touches it. At BlurStrength=0 the user can see
    // the source content rendered at ~0.667× of native (1/scale on a
    // 1.5× display) — "looks crisp but clearly at 0.5 of original res".
    //
    // The downstream pipeline (offscreen geometry, projection matrices,
    // blit destination) all switches to scaledBackgroundRect to match.
    if (renderInfo.framebuffers.size() != (iterationCount + 1) || renderInfo.textures[0]->size() != scaledBackgroundRect.size()
        || renderInfo.textures[0]->internalFormat() != textureFormat) {
        renderInfo.framebuffers.clear();
        renderInfo.textures.clear();

        glClearColor(0, 0, 0, 0);
        for (size_t i = 0; i <= iterationCount; ++i) {
            // Ensure the texture is at least 1×1 — at high iteration counts (level 5 = /32)
            // a small window could produce a zero-size texture and crash the driver.
            QSize texSize = scaledBackgroundRect.size() / (1 << i);
            texSize.setWidth(qMax(texSize.width(), 1));
            texSize.setHeight(qMax(texSize.height(), 1));
            auto texture = GLTexture::allocate(textureFormat, texSize);
            if (!texture) {
                qCWarning(KWIN_BLUR) << "Failed to allocate an offscreen texture";
                return;
            }
            texture->setFilter(GL_LINEAR);
            texture->setWrapMode(GL_CLAMP_TO_EDGE);

            auto framebuffer = std::make_unique<GLFramebuffer>(texture.get());
            if (!framebuffer->valid()) {
                qCWarning(KWIN_BLUR) << "Failed to create an offscreen framebuffer";
                return;
            }
            EglContext::currentContext()->pushFramebuffer(framebuffer.get());
            glClear(GL_COLOR_BUFFER_BIT);
            EglContext::currentContext()->popFramebuffer();
            renderInfo.textures.push_back(std::move(texture));
            renderInfo.framebuffers.push_back(std::move(framebuffer));
        }
    }

    // 4. Blit the background into framebuffers[0]
    // Source is logical (blitFromRenderTarget transforms it via viewport).
    // Destination is in the framebuffer's own pixel space — now device,
    // so map dirtyRect through viewport.scale() before translating.
    // A wobbly mesh can sample any point in its full deformed bounds even
    // when KWin only asks us to repaint the newly exposed strip. Capture the
    // complete surface, then clip the generated triangles to deviceRegion.
    const Region dirtyRegion = wobblySurface ? Region(Rect(backgroundRect))
#if defined(GLASS_X11)
                                             : deviceRegion.intersected(deviceBackgroundRect);
#else
                                             : viewport.mapFromDeviceCoordinatesContained(deviceRegion) & backgroundRect;
#endif
    for (const Rect& dirtyRect : dirtyRegion.rects()) {
#if defined(GLASS_X11)
        Q_UNUSED(dirtyRect)
        renderInfo.framebuffers[0]->blitFromRenderTarget(renderTarget, viewport,
            backgroundRect, QRect(QPoint(0, 0), scaledBackgroundRect.size()));
#else
        const QRect deviceDirtyRect = agSnapToPixelGrid(scaledRect(QRectF(dirtyRect), viewport.scale()));
        renderInfo.framebuffers[0]->blitFromRenderTarget(renderTarget, viewport, dirtyRect, deviceDirtyRect.translated(-scaledBackgroundRect.topLeft()));
#endif
    }

    // 5. Upload vertex geometry
    // First 6 vertices are the offscreen quad reused by every Kawase pass.
    // The rest are the onscreen geometry (one quad per effectiveShape rect).
    GLVertexBuffer* vbo = GLVertexBuffer::streamingBuffer();
    vbo->reset();
    vbo->setAttribLayout(std::span(GLVertexBuffer::GLVertex2DLayout), sizeof(GLVertex2D));

    const int vertexCount = wobblySurface ? static_cast<int>(wobblyVertices.size()) : effectiveShape.size() * 6;
    if (auto result = vbo->map<GLVertex2D>(6 + vertexCount)) {
        auto map = *result;

        size_t vboIndex = 0;

        // The geometry that will be blurred offscreen, in DEVICE pixels —
        // the offscreen framebuffers are now allocated at scaledBackgroundRect
        // size so the projection + geometry have to match or the blur
        // chain only fills 1/scale of each target.
        {
            const QRectF localRect = QRectF(0, 0, scaledBackgroundRect.width(), scaledBackgroundRect.height());

            const float x0 = localRect.left();
            const float y0 = localRect.top();
            const float x1 = localRect.right();
            const float y1 = localRect.bottom();

            const float u0 = x0 / scaledBackgroundRect.width();
            const float v0 = 1.0f - y0 / scaledBackgroundRect.height();
            const float u1 = x1 / scaledBackgroundRect.width();
            const float v1 = 1.0f - y1 / scaledBackgroundRect.height();

            // first triangle
            map[vboIndex++] = GLVertex2D {
                .position = QVector2D(x0, y0),
                .texcoord = QVector2D(u0, v0),
            };
            map[vboIndex++] = GLVertex2D {
                .position = QVector2D(x1, y1),
                .texcoord = QVector2D(u1, v1),
            };
            map[vboIndex++] = GLVertex2D {
                .position = QVector2D(x0, y1),
                .texcoord = QVector2D(u0, v1),
            };

            // second triangle
            map[vboIndex++] = GLVertex2D {
                .position = QVector2D(x0, y0),
                .texcoord = QVector2D(u0, v0),
            };
            map[vboIndex++] = GLVertex2D {
                .position = QVector2D(x1, y0),
                .texcoord = QVector2D(u1, v0),
            };
            map[vboIndex++] = GLVertex2D {
                .position = QVector2D(x1, y1),
                .texcoord = QVector2D(u1, v1),
            };
        }

        // Onscreen geometry. position is the final screen location used
        // for background sampling; texcoord is the undeformed local
        // coordinate used by the rounded-rect SDF, lens and highlight.
        if (wobblySurface) {
            for (const GLVertex2D& vertex : wobblyVertices) {
                map[vboIndex++] = vertex;
            }
        } else {
            for (const RectF& rect : effectiveShape) {
                const float x0 = rect.left();
                const float y0 = rect.top();
                const float x1 = rect.right();
                const float y1 = rect.bottom();

                const QVector2D topLeft(x0, y0);
                const QVector2D bottomRight(x1, y1);
                const QVector2D bottomLeft(x0, y1);
                const QVector2D topRight(x1, y0);

                map[vboIndex++] = GLVertex2D{.position = topLeft, .texcoord = topLeft};
                map[vboIndex++] = GLVertex2D{.position = bottomRight, .texcoord = bottomRight};
                map[vboIndex++] = GLVertex2D{.position = bottomLeft, .texcoord = bottomLeft};

                map[vboIndex++] = GLVertex2D{.position = topLeft, .texcoord = topLeft};
                map[vboIndex++] = GLVertex2D{.position = topRight, .texcoord = topRight};
                map[vboIndex++] = GLVertex2D{.position = bottomRight, .texcoord = bottomRight};
            }
        }

        vbo->unmap();
    } else {
        qCWarning(KWIN_BLUR) << "Failed to map vertex buffer";
        return;
    }

    vbo->bindArrays();

    // 6. Dual Kawase loop
    // At zero offset the final onscreen pass reads from framebuffers[0] (the
    // unblurred original) directly, so the Kawase chain is wasted GPU work.
    if (blurOffset > 0.0f) {
        // Intermediate passes replace their target; inherited blending
        // would accumulate stale translucent pixels on subsequent frames.
        glDisable(GL_BLEND);
        // The downsample pass of the dual Kawase algorithm: the background will be scaled down 50% every iteration.
        {
            ShaderManager::instance()->pushShader(m_downsamplePass.shader.get());

            QMatrix4x4 projectionMatrix;
            projectionMatrix.ortho(QRectF(0.0, 0.0, scaledBackgroundRect.width(), scaledBackgroundRect.height()));

            m_downsamplePass.shader->setUniform(m_downsamplePass.mvpMatrixLocation, projectionMatrix);
            // Scale by viewport.scale() so the Kawase tap spacing stays
            // visually constant after we moved framebuffers to device px.
            // halfpixel = 0.5/device_width is now 1/scale of what it was
            // at logical size, so without this multiplier the same
            // BlurStrength produces a tighter blur on HiDPI/fractional
            // displays.
            m_downsamplePass.shader->setUniform(m_downsamplePass.offsetLocation, float(blurOffset * viewport.scale()));

            for (size_t i = 1; i < renderInfo.framebuffers.size(); ++i) {
                const auto& read = renderInfo.framebuffers[i - 1];
                const auto& draw = renderInfo.framebuffers[i];

                const QVector2D halfpixel(0.5 / read->colorAttachment()->width(), 0.5 / read->colorAttachment()->height());
                m_downsamplePass.shader->setUniform(m_downsamplePass.halfpixelLocation, halfpixel);

                read->colorAttachment()->bind();

                GLFramebuffer::pushFramebuffer(draw.get());
                vbo->draw(GL_TRIANGLES, 0, 6);
            }

            ShaderManager::instance()->popShader();
        }

        // The upsample pass of the dual Kawase algorithm: the background will be scaled up 200% every iteration.
        {
            ShaderManager::instance()->pushShader(m_upsamplePass.shader.get());

            QMatrix4x4 projectionMatrix;
            projectionMatrix.ortho(QRectF(0.0, 0.0, scaledBackgroundRect.width(), scaledBackgroundRect.height()));

            m_upsamplePass.shader->setUniform(m_upsamplePass.mvpMatrixLocation, projectionMatrix);
            // Same scale compensation as the downsample pass — keeps the
            // upsample tap spacing consistent with the new device-px
            // framebuffer dimensions.
            m_upsamplePass.shader->setUniform(m_upsamplePass.offsetLocation, float(blurOffset * viewport.scale()));

            for (size_t i = renderInfo.framebuffers.size() - 1; i > 1; --i) {
                GLFramebuffer::popFramebuffer();
                const auto& read = renderInfo.framebuffers[i];

                const QVector2D halfpixel(0.5 / read->colorAttachment()->width(), 0.5 / read->colorAttachment()->height());
                m_upsamplePass.shader->setUniform(m_upsamplePass.halfpixelLocation, halfpixel);

                read->colorAttachment()->bind();

                vbo->draw(GL_TRIANGLES, 0, 6);
            }

            ShaderManager::instance()->popShader();
        }
    }

    // 7. Resolve per-window corner radius
    // KDecoration provides the client-declared corner radius; we override
    // it with kcfg values keyed by window type (dock / popup / normal).
    // Maximized full-screen apps keep sharp corners unless the user
    // opts in via RoundCornersOfMaximizedWindows.
    const QMatrix4x4 colorMatrix = dockSurface ? colorTransformMatrix(1.33, 1.0, 1.0) : m_colorMatrix;
    const float modulation = opacity * opacity;

    BorderRadius cornerRadius = w->window()->borderRadius();
    float topCornerRadius = 0.0;
    float bottomCornerRadius = 0.0;

    if (w->isDock()) {
        topCornerRadius = BlurConfig::dockCornerRadius();
        bottomCornerRadius = BlurConfig::dockCornerRadius();

    } else if (w->isTooltip() || w->isPopupWindow() || w->isMenu() || w->isDropdownMenu() || w->isPopupMenu() || w->isAppletPopup()) {
        topCornerRadius = BlurConfig::popupCornerRadius();
        bottomCornerRadius = BlurConfig::popupCornerRadius();

    } else {
        // A window is "maximized" when its frame fills the maximize area of
        // its own screen / desktop — checked live each frame (no cached
        // state to lag a maximize/restore). isFullScreen() alone misses
        // this, so without it a maximized window keeps rounded corners even
        // when the user opted out via RoundCornersOfMaximizedWindows.
        // Uses the per-window clientArea overload so multi-monitor setups
        // resolve against the window's actual screen. Mirrors Better Blur.
        const bool isMaximized = effects->clientArea(MaximizeArea, w).toRect() == w->frameGeometry().toRect();
        if ((!w->isFullScreen() && !isMaximized) || BlurConfig::roundCornersOfMaximizedWindows()) {
            topCornerRadius = BlurConfig::windowCornerRadius();
            bottomCornerRadius = BlurConfig::windowCornerRadius();
        }
    }

    QRectF surfaceRect = w->frameGeometry();
    if (blurInfo.clientShape.has_value()) {
        topCornerRadius = bottomCornerRadius = blurInfo.clientShape->cornerRadius();
        surfaceRect = blurInfo.clientShape->surfaceRect().translated(w->pos());
        cornerRadius = BorderRadius(topCornerRadius, topCornerRadius,
                                    bottomCornerRadius, bottomCornerRadius);
    }

    // ShapeCorners publishes its animated geometry during prePaintWindow.
    // Follow the actual cutout, including inactive/maximized/excluded states,
    // without changing either effect's saved preferences (#89).
    float cornerSquircle = 0.0f;
    const auto shape = w->property("_mttkde_corner_shape_v1").toList();
    if (shape.size() == 2) {
        surfaceRect = w->frameGeometry();
        topCornerRadius = bottomCornerRadius = std::max(0.0f, shape[0].toFloat());
        cornerSquircle = std::clamp(shape[1].toFloat(), 0.0f, 1.0f);
        cornerRadius = BorderRadius(topCornerRadius, topCornerRadius,
                                    bottomCornerRadius, bottomCornerRadius);
    }

    // Clamp the radius for narrow / short windows so the SDF doesn't
    // wrap around onto itself when r > half-dimension.
    if (topCornerRadius > 0 || bottomCornerRadius > 0) {
        const QRectF frame = surfaceRect;
        const float winWidth = frame.width();
        const float winHeight = frame.height();
        bool isOverRounded = (topCornerRadius + bottomCornerRadius) > winHeight || (topCornerRadius * 2) > winWidth;

        if (isOverRounded) {
            float minRadius = std::min(winWidth, winHeight) / 2.0f;
            topCornerRadius = std::min(topCornerRadius, minRadius);
            bottomCornerRadius = std::min(bottomCornerRadius, minRadius);
        }

        cornerRadius = BorderRadius(topCornerRadius, // top left
            topCornerRadius, // top right
            bottomCornerRadius, // bottom right
            bottomCornerRadius // bottom left
        );
    }

    // 8. Onscreen pass
    ShaderManager::instance()->pushShader(m_roundedOnscreenPass.shader.get());

    QMatrix4x4 projectionMatrix = viewport.projectionMatrix();
#if defined(GLASS_X11)
    projectionMatrix.translate(deviceBackgroundRect.x(), deviceBackgroundRect.y());
#else
    projectionMatrix.translate(scaledBackgroundRect.x(), scaledBackgroundRect.y());
#endif

    // Balance the final downsample push from the Kawase loop above. Skipped
    // alongside it when offset=0 so the framebuffer stack stays balanced.
    if (blurOffset > 0.0f) {
        GLFramebuffer::popFramebuffer();
    }

    // framebuffers[0] is the original unblurred background capture (full res).
    // framebuffers[1] is the Kawase-blurred result (half res).
    // At offset 0 (no blur) read the full-res original to avoid downscaling artifacts.
    const auto& read = (blurOffset > 0.0f && renderInfo.framebuffers.size() > 1) ? renderInfo.framebuffers[1] : renderInfo.framebuffers[0];

    const QVector2D halfpixel(0.5 / read->colorAttachment()->width(), 0.5 / read->colorAttachment()->height());

    const QRectF transformedRect = QRectF {
        w->x() + (surfaceRect.x() - w->x()) * data.xScale() + data.xTranslation(),
        w->y() + (surfaceRect.y() - w->y()) * data.yScale() + data.yTranslation(),
        surfaceRect.width() * data.xScale(),
        surfaceRect.height() * data.yScale(),
    };
    // Floor to integer device pixels so the SDF rounded corners are always
    // pixel-aligned — prevents subpixel border artifacts that shift with
    // window position.
    const QRectF nativeBoxF = agSnapToPixelGridF(scaledRect(transformedRect, viewport.scale()))
#if defined(GLASS_X11)
        .translated(-deviceBackgroundRect.topLeft());
#else
        .translated(-scaledBackgroundRect.topLeft());
#endif
    const QRectF nativeBox(std::floor(nativeBoxF.x()), std::floor(nativeBoxF.y()), std::floor(nativeBoxF.width()), std::floor(nativeBoxF.height()));
    const BorderRadius nativeCornerRadius = cornerRadius.scaled(viewport.scale()).rounded();

    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.mvpMatrixLocation, projectionMatrix);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.colorMatrixLocation, colorMatrix);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.halfpixelLocation, halfpixel);

    // The Gaussian finish is a fixed reconstruction filter in source texels.
    // Scale compensation belongs to the Kawase passes; offset gates bypass.
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.offsetLocation, float(blurOffset * viewport.scale()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.boxLocation,
        QVector4D(nativeBox.x() + nativeBox.width() * 0.5, nativeBox.y() + nativeBox.height() * 0.5, nativeBox.width() * 0.5, nativeBox.height() * 0.5));

    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.cornerSquircleLocation, cornerSquircle);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.cornerRadiusLocation, nativeCornerRadius.toVector());
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.opacityLocation, modulation);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.blurSizeLocation, QVector2D(nativeBox.width(), nativeBox.height()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.rgbDriftStrengthLocation,
        float(optics.rgbDrift * viewport.scale()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.magnifyGlassStrengthLocation, optics.refraction);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.refractionWidthLocation, float(optics.refractionWidth * viewport.scale()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.highlightWidthLocation, float(optics.highlightWidth * viewport.scale()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.highlightStrengthLocation, optics.highlightStrength);
    // Panels and the Dock retain untinted glass under every material.
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.darkGradientOverlayLocation,
        int(m_darkGradientOverlay && !w->isDock()));
    const QPalette windowPalette = w->window()->palette();
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.centerOpacityLocation, centerOpacity);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.dockSurfaceLocation, int(dockSurface));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.backgroundSizeLocation,
        QVector2D(scaledBackgroundRect.width(), scaledBackgroundRect.height()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.gradientTopLocation,
        gradientColorForPalette(m_gradientTop, m_gradientTopDark, windowPalette));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.gradientCenterLocation,
        gradientColorForPalette(m_gradientCenter, m_gradientCenterDark, windowPalette));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.gradientCenterPositionLocation, m_gradientCenterPosition);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.gradientBottomLocation,
        gradientColorForPalette(m_gradientBottom, m_gradientBottomDark, windowPalette));

    read->colorAttachment()->bind();

    glEnable(GL_BLEND);
    glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);

    vbo->draw(GL_TRIANGLES, 6, vertexCount);

    glDisable(GL_BLEND);

    ShaderManager::instance()->popShader();

    // 9. Grain pass (optional)
    // v0.62.0 used NoiseStrength 1: rand() % 1 produces a zero texture.
    // Skipping that no-op preserves the Dock while windows keep their grain.
    if (!dockSurface && m_noiseStrength > 0) {
        // Additive noise over the blurred image. Masks banding artefacts
        // that show up in smooth gradients after heavy blur.

        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE);

        if (GLTexture* noiseTexture = ensureNoiseTexture()) {
            ShaderManager::instance()->pushShader(m_noisePass.shader.get());

            QMatrix4x4 projectionMatrix = viewport.projectionMatrix();
#if defined(GLASS_X11)
            projectionMatrix.translate(deviceBackgroundRect.x(), deviceBackgroundRect.y());
#else
            projectionMatrix.translate(scaledBackgroundRect.x(), scaledBackgroundRect.y());
#endif

            m_noisePass.shader->setUniform(m_noisePass.mvpMatrixLocation, projectionMatrix);
            m_noisePass.shader->setUniform(m_noisePass.noiseTextureSizeLocation, QVector2D(noiseTexture->width(), noiseTexture->height()));

            m_noisePass.shader->setUniform(m_noisePass.boxLocation, QVector4D(nativeBox.center().x(), nativeBox.center().y(), nativeBox.width() * 0.5, nativeBox.height() * 0.5));
            m_noisePass.shader->setUniform(m_noisePass.blurSizeLocation, QVector2D(nativeBox.width(), nativeBox.height()));
            m_noisePass.shader->setUniform(m_noisePass.cornerRadiusLocation, nativeCornerRadius.toVector());
            m_noisePass.shader->setUniform(m_noisePass.cornerSquircleLocation, cornerSquircle);
            m_noisePass.shader->setUniform(m_noisePass.opacityLocation,
                modulation * centerOpacity * (dockSurface ? 0.25f : 1.0f));
            noiseTexture->bind();

            vbo->draw(GL_TRIANGLES, 6, vertexCount);

            ShaderManager::instance()->popShader();
        }

        glDisable(GL_BLEND);
    }

    vbo->unbindArrays();
}

// Status queries

/// Only "active" once every shader compiled + the screen is unlocked.
/// Screen-lock blocks all blur for both perf and visual reasons (the
/// lock screen has its own opaque background).
bool BlurEffect::isActive() const
{
    return m_valid && !effects->isScreenLocked();
}

/// We always need GL compositing, never direct scanout.
bool BlurEffect::blocksDirectScanout() const
{
    return false;
}

} // namespace KWin

#include "moc_effect.cpp"
