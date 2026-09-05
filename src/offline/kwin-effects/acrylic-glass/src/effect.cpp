/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-FileCopyrightText: 2011 Philipp Knechtges <philipp-dev@knechtges.com>
    SPDX-FileCopyrightText: 2018 Alex Nemeth <alex.nemeth329@gmail.com>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "effect.h"
// KConfigSkeleton
#include "glassconfig.h"

#include "core/pixelgrid.h"
#include "core/rendertarget.h"
#include "core/renderviewport.h"
#include "effect/effecthandler.h"
#include "opengl/glplatform.h"
#include "scene/decorationitem.h"
#include "scene/scene.h"
#include "scene/surfaceitem.h"
#include "scene/windowitem.h"
#if ACRYLIC_GLASS_KWIN_6_7
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
#endif

#include <QGuiApplication>
#include <QMatrix4x4>
#include <QScreen>
#include <QTime>
#include <QTimer>
#include <QWindow>
#include <cmath> // for ceil()
#include <cstdlib>

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

namespace KWin {

#if ACRYLIC_GLASS_KWIN_6_7
/// 6.7 removed the global scaledRect() helper (it lived in
/// effect/globals.h pre-6.7). Re-provide it verbatim so the three call
/// sites below stay version-agnostic; snapToPixelGrid* are still in the
/// KWin headers.
inline QRectF scaledRect(const QRectF& rect, qreal scale)
{
    return QRectF{rect.x() * scale, rect.y() * scale, rect.width() * scale, rect.height() * scale};
}
#endif

/// X11 atom name we listen to for the blur-behind property protocol.
static const QByteArray s_blurAtomName = QByteArrayLiteral("_KDE_NET_WM_BLUR_BEHIND_REGION");

// Static singleton storage (definitions live here, declarations in .h).
// The protocol-manager singletons only exist on the pre-6.7 API; 6.7
// registers a capability on the shared backgroundEffectManager instead.
#if !ACRYLIC_GLASS_KWIN_6_7
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
        ShaderTrait::MapTexture, QStringLiteral(":/effects/liquidglass/shaders/glass.vert"), QStringLiteral(":/effects/liquidglass/shaders/glass.frag"));
    if (!m_roundedOnscreenPass.shader) {
        qCWarning(KWIN_BLUR) << "Failed to load onscreen pass shader (null)";
        return;
#if !ACRYLIC_GLASS_KWIN_6_7
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
        m_roundedOnscreenPass.cornerRadiusLocation = m_roundedOnscreenPass.shader->uniformLocation("cornerRadius");
        m_roundedOnscreenPass.opacityLocation = m_roundedOnscreenPass.shader->uniformLocation("opacity");
        m_roundedOnscreenPass.blurSizeLocation = m_roundedOnscreenPass.shader->uniformLocation("blurSize");
        m_roundedOnscreenPass.rgbDriftStrengthLocation = m_roundedOnscreenPass.shader->uniformLocation("rgbDriftStrength");
        m_roundedOnscreenPass.magnifyGlassStrengthLocation = m_roundedOnscreenPass.shader->uniformLocation("magnifyGlassStrength");
        m_roundedOnscreenPass.refractionWidthLocation = m_roundedOnscreenPass.shader->uniformLocation("refractionWidth");
        m_roundedOnscreenPass.highlightWidthLocation = m_roundedOnscreenPass.shader->uniformLocation("highlightWidth");
        m_roundedOnscreenPass.highlightStrengthLocation = m_roundedOnscreenPass.shader->uniformLocation("highlightStrength");
        m_roundedOnscreenPass.blurTypeLocation = m_roundedOnscreenPass.shader->uniformLocation("blurType");

        qCDebug(KWIN_BLUR) << "Onscreen shader uniforms:"
                           << "mvp=" << m_roundedOnscreenPass.mvpMatrixLocation << "color=" << m_roundedOnscreenPass.colorMatrixLocation
                           << "offset=" << m_roundedOnscreenPass.offsetLocation << "halfpx=" << m_roundedOnscreenPass.halfpixelLocation
                           << "box=" << m_roundedOnscreenPass.boxLocation << "corner=" << m_roundedOnscreenPass.cornerRadiusLocation
                           << "opacity=" << m_roundedOnscreenPass.opacityLocation << "blurSize=" << m_roundedOnscreenPass.blurSizeLocation;
    }

    // Dual Kawase downsample pass
    m_downsamplePass.shader = ShaderManager::instance()->generateShaderFromFile(
        ShaderTrait::MapTexture, QStringLiteral(":/effects/liquidglass/shaders/vertex.vert"), QStringLiteral(":/effects/liquidglass/shaders/downsample.frag"));
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
        ShaderTrait::MapTexture, QStringLiteral(":/effects/liquidglass/shaders/vertex.vert"), QStringLiteral(":/effects/liquidglass/shaders/upsample.frag"));
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
        ShaderTrait::MapTexture, QStringLiteral(":/effects/liquidglass/shaders/vertex.vert"), QStringLiteral(":/effects/liquidglass/shaders/noise.frag"));
    if (!m_noisePass.shader) {
        qCWarning(KWIN_BLUR) << "Failed to load noise pass shader";
        return;
    } else {
        m_noisePass.mvpMatrixLocation = m_noisePass.shader->uniformLocation("modelViewProjectionMatrix");
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
#if ACRYLIC_GLASS_KWIN_6_7
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
    connect(effects, &EffectsHandler::viewRemoved, this, &BlurEffect::slotViewRemoved);
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
#if ACRYLIC_GLASS_KWIN_6_7
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
    m_blurType = static_cast<int>(BlurConfig::acrylicGlassType());
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

    // X11: read the _KDE_NET_WM_BLUR_BEHIND_REGION cardinal array.
    // Layout is repeating (x, y, w, h) tuples of 32-bit cardinals.
    // EffectWindow::readProperty() was removed from the Wayland build in
    // 6.7, so this client-property path only compiles where it still
    // exists: any pre-6.7 build, or a dedicated X11 (GLASS_X11) target.
#if KWIN_BUILD_X11 && (!ACRYLIC_GLASS_KWIN_6_7 || defined(GLASS_X11))
    if (net_wm_blur_region != XCB_ATOM_NONE) {
        const QByteArray value = w->readProperty(net_wm_blur_region, XCB_ATOM_CARDINAL, 32);
        Region region;

        if (value.size() > 0 && !(value.size() % (4 * sizeof(uint32_t)))) {
            const uint32_t* cardinals = reinterpret_cast<const uint32_t*>(value.constData());
            for (unsigned int i = 0; i < value.size() / sizeof(uint32_t);) {
                int x = cardinals[i++];
                int y = cardinals[i++];
                int w = cardinals[i++];
                int h = cardinals[i++];
                region += Xcb::fromXNative(Rect(x, y, w, h)).toRect();
            }
        }

        if (!value.isNull()) {
            content = region;
        }
    }
#endif

    // Wayland: prefer the protocol-driven blur/contrast surface state.
    if (SurfaceInterface* surface = w->surface()) {
#if ACRYLIC_GLASS_KWIN_6_7
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

    // Decoration-side blur: opt-in via the KDecoration3 protocol, else
    // implicit for normal windows (skip docks / menus / popups so their
    // own opaque chrome doesn't double-blur).
    if (m_blurDecorations && w->decorationHasAlpha() && decorationSupportsBlurBehind(w)) {
        frame = decorationBlurRegion(w);
    } else if (m_blurDecorations && !(w->isDock() || w->isMenu() || w->isDropdownMenu() || w->isPopupMenu() || w->isPopupWindow())) {
        frame = Rect(w->frameGeometry().translated(-w->x(), -w->y()).toRect());
    }

    // Commit (or evict).
    if (content.has_value() || frame.has_value()) {
        BlurEffectData& data = m_windows[w];
        data.content = content;
        data.frame = frame;
        data.colorMatrix = colorTransformMatrix(saturation.value_or(1.0), contrast.value_or(1.0), 1.0);
        data.windowEffect = ItemEffect(w->windowItem());
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

#if !ACRYLIC_GLASS_KWIN_6_7
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

    if (auto it = windowBlurChangedConnections.find(w); it != windowBlurChangedConnections.end()) {
        disconnect(*it);
        windowBlurChangedConnections.erase(it);
    }

#if !ACRYLIC_GLASS_KWIN_6_7
    if (auto it = windowContrastChangedConnections.find(w); it != windowContrastChangedConnections.end()) {
        disconnect(*it);
        windowContrastChangedConnections.erase(it);
    }
#endif

    if (auto it = windowFrameGeometryChangedConnections.find(w); it != windowFrameGeometryChangedConnections.end()) {
        disconnect(*it);
        windowFrameGeometryChangedConnections.erase(it);
    }
}

/// Drop the per-view scratch buffers (textures + framebuffers) for an
/// output that just disappeared. Each window's render map is keyed by
/// RenderView*, so we walk every window once.
void BlurEffect::slotViewRemoved(KWin::RenderView* view)
{
    for (auto& [window, data] : m_windows) {
        if (auto it = data.render.find(view); it != data.render.end()) {
            effects->makeOpenGLContextCurrent();
            data.render.erase(it);
        }
    }
}

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

        if (content.has_value()) {
            if (content->isEmpty()) {
                // Empty optional → "blur everything inside the content rect".
                region = Rect(w->contentsRect().toRect());
            } else {
                region = content->translated(w->contentsRect().topLeft().toPoint()) & w->contentsRect().toRect();
            }

            if (frame.has_value()) {
                region += frame.value();
            }
        } else if (frame.has_value()) {
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
    m_currentView = data.view;

    effects->prePaintScreen(data ACRYLIC_GLASS_PRESENT_TIME_ARG);
}

/// Expand the dirty / opaque regions so the Kawase chain has the
/// surrounding pixels it needs to sample, and so KWin doesn't occlude
/// (= skip) the background behind our blur area as a perf optimisation.
void BlurEffect::prePaintWindow(RenderView* view, EffectWindow* w, WindowPrePaintData& data ACRYLIC_GLASS_PRESENT_TIME_PARAM)
{
    effects->prePaintWindow(view, w, data ACRYLIC_GLASS_PRESENT_TIME_ARG);

#if ACRYLIC_GLASS_KWIN_6_7
    // On KWin 6.7+ the ext_background_effect_v1 machinery owns the
    // dirty/opaque bookkeeping, so no manual pass is needed. The
    // WindowPrePaintData::deviceOpaque / devicePaint members it poked are
    // gone; the effect just marks the window translucent so KWin paints
    // the background we sample. Matches upstream kwin-effects-glass.
    Q_UNUSED(view)
    if (!blurRegion(w).isEmpty()) {
        data.setTranslucent();
    }
#else
    // 1. The visible blur area for this window, mapped to device px.
    const Region blurArea = view->mapToDeviceCoordinatesAligned(QRectF(blurRegion(w).boundingRect()).translated(w->pos()));

    if (!blurArea.isEmpty()) {
        // 2. FORCE TRANSPARENCY: Remove the blur area from the opaque
        // region. Otherwise KWin "occludes" (= skips) the rendering of
        // whatever sits behind us, and our blur reads stale pixels.
        data.deviceOpaque -= blurArea;

        // 3. EXPAND PAINT REGION: Pull in pixels from slightly outside
        // the visible bounds so refraction / Kawase taps near the rim
        // sample real content, not whatever was left in the buffer.
        Region expandedBlur = blurArea;
        for (const Rect& rect : blurArea.rects()) {
            expandedBlur += rect.adjusted(-m_expandSize, -m_expandSize, m_expandSize, m_expandSize);
        }

        // Ensure the compositor actually paints the background we need to sample.
        data.devicePaint += (expandedBlur - data.deviceOpaque);
    }

    // Carry over the blur "damage" to windows lower in the stack so they
    // also repaint — otherwise a moving window behind a stationary glass
    // surface leaves trails.
    if (m_paintedDeviceArea.intersects(blurArea) || data.devicePaint.intersects(blurArea)) {
        data.devicePaint += blurArea;
    }

    m_currentDeviceBlur += blurArea;
    m_paintedDeviceArea -= data.deviceOpaque;
    m_paintedDeviceArea += data.devicePaint;
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

    // Skip transformed windows — Plasma's overview / present-windows
    // effects scale and translate windows around, and blurring while
    // they're mid-animation reads garbage from the background fb.
    bool scaled = !qFuzzyCompare(data.xScale(), 1.0) || !qFuzzyCompare(data.yScale(), 1.0);
    bool translated = data.xTranslation() || data.yTranslation();

    if ((scaled || (translated || (mask & PAINT_WINDOW_TRANSFORMED))) && !w->data(WindowForceBlurRole).toBool()) {
        return false;
    }

    return true;
}

/// Delegate to ``blur()`` (which handles its own shouldBlur gate
/// internally), then defer to KWin's default to draw the actual window
/// content on top of the blurred background.
void BlurEffect::drawWindow(
    const RenderTarget& renderTarget, const RenderViewport& viewport, EffectWindow* w, int mask, const Region& deviceRegion, WindowPaintData& data)
{
    blur(renderTarget, viewport, w, mask, deviceRegion, data);

    effects->drawWindow(renderTarget, viewport, w, mask, deviceRegion, data);
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

    // 2. Effective blur shape
    // If the window is transformed (scaled / translated by an effect such
    // as overview), the shape has to follow.
    Region blurShape = blurRegion(w).translated(w->pos().toPoint());

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

    const QRect backgroundRect = blurShape.boundingRect();
    const QRect scaledBackgroundRect = snapToPixelGrid(scaledRect(backgroundRect, viewport.scale()));
    const QRect deviceBackgroundRect = snapToPixelGrid(viewport.mapToDeviceCoordinates(backgroundRect));
    const auto opacity = data.opacity();

    // Intersect the shape with the deviceRegion clip — empty after the
    // intersection means everything is clipped and there's nothing to draw.
    QList<RectF> effectiveShape;
    effectiveShape.reserve(blurShape.rects().size());
    if (deviceRegion != Region::infinite()) {
        for (const Rect& clipRect : deviceRegion.rects()) {
            const RectF deviceClipRect = clipRect.translated(-deviceBackgroundRect.topLeft());
            for (const Rect& shapeRect : blurShape.rects()) {
                const RectF deviceShapeRect = shapeRect.translated(-backgroundRect.topLeft()).scaled(viewport.scale()).rounded();
                if (const QRectF intersected = deviceClipRect.intersected(deviceShapeRect); !intersected.isEmpty()) {
                    effectiveShape.append(intersected);
                }
            }
        }
    } else {
        for (const Rect& rect : blurShape.rects()) {
            effectiveShape.append(rect.translated(-backgroundRect.topLeft()).scaled(viewport.scale()).rounded());
        }
    }
    if (effectiveShape.isEmpty()) {
        return;
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
    if (renderInfo.framebuffers.size() != (m_iterationCount + 1) || renderInfo.textures[0]->size() != scaledBackgroundRect.size()
        || renderInfo.textures[0]->internalFormat() != textureFormat) {
        renderInfo.framebuffers.clear();
        renderInfo.textures.clear();

        glClearColor(0, 0, 0, 0);
        for (size_t i = 0; i <= m_iterationCount; ++i) {
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
    const Region dirtyRegion = viewport.mapFromDeviceCoordinatesContained(deviceRegion) & backgroundRect;
    for (const Rect& dirtyRect : dirtyRegion.rects()) {
        const QRect deviceDirtyRect = snapToPixelGrid(scaledRect(QRectF(dirtyRect), viewport.scale()));
        renderInfo.framebuffers[0]->blitFromRenderTarget(renderTarget, viewport, dirtyRect, deviceDirtyRect.translated(-scaledBackgroundRect.topLeft()));
    }

    // 5. Upload vertex geometry
    // First 6 vertices are the offscreen quad reused by every Kawase pass.
    // The rest are the onscreen geometry (one quad per effectiveShape rect).
    GLVertexBuffer* vbo = GLVertexBuffer::streamingBuffer();
    vbo->reset();
    vbo->setAttribLayout(std::span(GLVertexBuffer::GLVertex2DLayout), sizeof(GLVertex2D));

    const int vertexCount = effectiveShape.size() * 6;
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

        // The geometry that will be painted on screen, in device pixels.
        for (const QRectF& rect : effectiveShape) {
            const float x0 = rect.left();
            const float y0 = rect.top();
            const float x1 = rect.right();
            const float y1 = rect.bottom();

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

        vbo->unmap();
    } else {
        qCWarning(KWIN_BLUR) << "Failed to map vertex buffer";
        return;
    }

    vbo->bindArrays();

    // 6. Dual Kawase loop
    // At zero offset the final onscreen pass reads from framebuffers[0] (the
    // unblurred original) directly, so the Kawase chain is wasted GPU work.
    if (m_offset > 0.0f) {
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
            m_downsamplePass.shader->setUniform(m_downsamplePass.offsetLocation, float(m_offset * viewport.scale()));

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
            m_upsamplePass.shader->setUniform(m_upsamplePass.offsetLocation, float(m_offset * viewport.scale()));

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
    const QMatrix4x4& colorMatrix = m_colorMatrix;
    const float modulation = opacity * opacity;

    BorderRadius cornerRadius = w->window()->borderRadius();
    float topCornerRadius = 0.0;
    float bottomCornerRadius = 0.0;

    if (w->isDock()) {
        topCornerRadius = BlurConfig::dockCornerRadius();
        bottomCornerRadius = BlurConfig::dockCornerRadius();

    } else if (w->isTooltip() || w->isPopupWindow() || w->isMenu() || w->isDropdownMenu() || w->isPopupMenu()) {
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

    // Clamp the radius for narrow / short windows so the SDF doesn't
    // wrap around onto itself when r > half-dimension.
    if (topCornerRadius > 0 || bottomCornerRadius > 0) {
        const QRectF frame = w->frameGeometry();
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
    projectionMatrix.translate(scaledBackgroundRect.x(), scaledBackgroundRect.y());

    // Balance the final downsample push from the Kawase loop above. Skipped
    // alongside it when offset=0 so the framebuffer stack stays balanced.
    if (m_offset > 0.0f) {
        GLFramebuffer::popFramebuffer();
    }

    // framebuffers[0] is the original unblurred background capture (full res).
    // framebuffers[1] is the Kawase-blurred result (half res).
    // At offset 0 (no blur) read the full-res original to avoid downscaling artifacts.
    const auto& read = (m_offset > 0.0f && renderInfo.framebuffers.size() > 1) ? renderInfo.framebuffers[1] : renderInfo.framebuffers[0];

    const QVector2D halfpixel(0.5 / read->colorAttachment()->width(), 0.5 / read->colorAttachment()->height());

    const QRectF transformedRect = QRectF {
        w->frameGeometry().x() + data.xTranslation(),
        w->frameGeometry().y() + data.yTranslation(),
        w->frameGeometry().width() * data.xScale(),
        w->frameGeometry().height() * data.yScale(),
    };
    // Floor to integer device pixels so the SDF rounded corners are always
    // pixel-aligned — prevents subpixel border artifacts that shift with
    // window position.
    const QRectF nativeBoxF = snapToPixelGridF(scaledRect(transformedRect, viewport.scale())).translated(-scaledBackgroundRect.topLeft());
    const QRectF nativeBox(std::floor(nativeBoxF.x()), std::floor(nativeBoxF.y()), std::floor(nativeBoxF.width()), std::floor(nativeBoxF.height()));
    const BorderRadius nativeCornerRadius = cornerRadius.scaled(viewport.scale()).rounded();

    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.mvpMatrixLocation, projectionMatrix);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.colorMatrixLocation, colorMatrix);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.halfpixelLocation, halfpixel);

    // Same scale compensation as the Kawase passes — the onscreen blur
    // kernel (Gaussian/Box/Lens) uses offset * 3 * texel as the tap
    // radius, and texel = 1/device_width, so without scale the kernel
    // tightens proportionally to viewport.scale() on HiDPI.
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.offsetLocation, float(m_offset * viewport.scale()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.boxLocation,
        QVector4D(nativeBox.x() + nativeBox.width() * 0.5, nativeBox.y() + nativeBox.height() * 0.5, nativeBox.width() * 0.5, nativeBox.height() * 0.5));

    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.cornerRadiusLocation, nativeCornerRadius.toVector());
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.opacityLocation, modulation);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.blurSizeLocation, QVector2D(nativeBox.width(), nativeBox.height()));
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.rgbDriftStrengthLocation, m_rgbDriftStrength);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.magnifyGlassStrengthLocation, m_magnifyGlassStrength);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.refractionWidthLocation, m_refractionWidth);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.highlightWidthLocation, m_highlightWidth);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.highlightStrengthLocation, m_highlightStrength);
    m_roundedOnscreenPass.shader->setUniform(m_roundedOnscreenPass.blurTypeLocation, m_blurType);

    read->colorAttachment()->bind();

    glEnable(GL_BLEND);
    glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);

    vbo->draw(GL_TRIANGLES, 6, vertexCount);

    glDisable(GL_BLEND);

    ShaderManager::instance()->popShader();

    // 9. Grain pass (optional)
    if (m_noiseStrength > 0) {
        // Additive noise over the blurred image. Masks banding artefacts
        // that show up in smooth gradients after heavy blur.

        glEnable(GL_BLEND);
        if (opacity < 1.0) {
            glBlendFunc(GL_CONSTANT_ALPHA, GL_ONE);
        } else {
            glBlendFunc(GL_ONE, GL_ONE);
        }

        if (GLTexture* noiseTexture = ensureNoiseTexture()) {
            ShaderManager::instance()->pushShader(m_noisePass.shader.get());

            QMatrix4x4 projectionMatrix = viewport.projectionMatrix();
            projectionMatrix.translate(scaledBackgroundRect.x(), scaledBackgroundRect.y());

            m_noisePass.shader->setUniform(m_noisePass.mvpMatrixLocation, projectionMatrix);
            m_noisePass.shader->setUniform(m_noisePass.noiseTextureSizeLocation, QVector2D(noiseTexture->width(), noiseTexture->height()));

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
