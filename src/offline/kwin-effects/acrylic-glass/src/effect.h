/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-FileCopyrightText: 2018 Alex Nemeth <alex.nemeth329@gmail.com>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include "effect/effect.h"
#include "opengl/glutils.h"
#include "scene/item.h"

#include <QList>
#include <QStringList>

#include <unordered_map>

namespace KWin {

class BlurManagerInterface;
class ContrastManagerInterface;

// Per-view blur scratch space

/**
 * Render targets that the Dual Kawase chain owns for a single RenderView.
 *
 * One BlurRenderData is allocated per view per blurred window. Textures
 * and framebuffers are paired: textures[i] is the colour attachment of
 * framebuffers[i]. textures[0] holds the unblurred capture of whatever
 * sits behind the window — the rest of the chain stores the progressive
 * Kawase downsample / upsample steps.
 *
 * Both vectors keep ``m_iterationCount + 1`` entries; the size is rebuilt
 * whenever the iteration count, window dimensions, or texture format
 * change (see BlurEffect::blur for the realloc gate).
 */
struct BlurRenderData
{
    std::vector<std::unique_ptr<GLTexture>> textures;
    std::vector<std::unique_ptr<GLFramebuffer>> framebuffers;
};

/**
 * Per-window state cached across frames.
 *
 * Carries the masked regions, the per-view render data, the bookkeeping
 * ItemEffect used to participate in KWin's scene graph, and the optional
 * colour matrix applied when contrast / saturation / brightness differ
 * from identity. Lifetime is tied to the EffectWindow* key in
 * BlurEffect::m_windows; entries are erased in slotWindowDeleted /
 * slotViewRemoved.
 */
struct BlurEffectData
{
    /** Subregion of the window content marked as blur-able by the client. */
    std::optional<Region> content;

    /** Subregion of the server-side decoration marked as blur-able. */
    std::optional<Region> frame;

    /**
     * Render scratch space keyed by the view it belongs to. Different
     * outputs can have different colour spaces / scales, so one shared
     * pool wouldn't survive multi-monitor setups.
     */
    std::unordered_map<RenderView*, BlurRenderData> render;

    /** Scene-graph handle that keeps the effect alive while the window is. */
    ItemEffect windowEffect;

    /**
     * Concatenated saturation × contrast × brightness transform. Empty
     * (and therefore identity) when all three settings are 1.0.
     */
    std::optional<QMatrix4x4> colorMatrix;
};

// BlurEffect — Dual Kawase + rounded-rect SDF compositor

/**
 * Acrylic Glass: macOS-Tahoe-styled blur effect for KWin.
 *
 * Pipeline per blurred window per frame:
 *   1. Capture the pixels behind the window into framebuffers[0]
 *      (device-resolution, see effect.cpp comments around the
 *      ``scaledBackgroundRect`` allocation for the rationale).
 *   2. Run Dual Kawase: ``m_iterationCount`` downsample passes
 *      (each halves resolution) followed by the same number of upsample
 *      passes back to framebuffers[1]. Skipped entirely when
 *      ``m_offset == 0`` — the onscreen pass reads framebuffers[0]
 *      directly for a pixel-perfect 1:1 passthrough.
 *   3. Final onscreen pass: glass.frag samples the blurred (or
 *      unblurred) source, masks against the rounded-rect SDF,
 *      applies the RGB drift / magnify lens / rim highlight knobs, and
 *      blends the result into the screen.
 *
 * Configuration lives in ``glass.kcfg`` (read via BlurConfig). User-
 * facing knobs map to ``m_*`` fields below — see ``reconfigure``.
 */
class BlurEffect : public KWin::Effect
{
    Q_OBJECT

public:
    // Construction / lifecycle

    /// Loads the shaders, sets up the Wayland blur / contrast managers,
    /// and validates that we have a usable GL context. Sets ``m_valid``
    /// only after every pass shader compiles cleanly.
    BlurEffect();
    ~BlurEffect() override;

    /// True iff KWin's OpenGL compositing backend supports the features
    /// we need (GLSL, FBO, GL_LINEAR-filtered RGBA8 textures). Called by
    /// KWin before the effect is constructed.
    static bool supported();

    /// True iff the effect should be loaded out-of-the-box, before the
    /// user touches any kcfg. Constant ``true`` for our build.
    static bool enabledByDefault();

    // Effect interface overrides

    /// Re-read every kcfg-driven knob (blur strength, drift strength,
    /// corner radii, etc.) and rebuild any derived state. Called on
    /// config changes and once at construction.
    void reconfigure(ReconfigureFlags flags) override;

    /// Marks the whole screen as "dirty under our window" so KWin
    /// schedules a repaint of the area behind a window we'll blur.
    void prePaintScreen(ScreenPrePaintData& data, std::chrono::milliseconds presentTime) override;

    /// Per-window setup before paint: extends the dirty region by the
    /// Kawase expand size so taps near the edges don't sample stale
    /// content from outside.
    void prePaintWindow(RenderView* view, EffectWindow* w, WindowPrePaintData& data, std::chrono::milliseconds presentTime) override;

    /// The main entry point — KWin asks us to paint window ``w``; we
    /// either delegate to ``blur()`` (when blur is wanted) or fall back
    /// to the default opaque draw.
    void drawWindow(const RenderTarget& renderTarget, const RenderViewport& viewport, EffectWindow* w, int mask, const Region& deviceRegion,
        WindowPaintData& data) override;

    /// Tells KWin we provide the ``Blur`` Feature — kcm/effects UI
    /// then groups us under the blur category.
    bool provides(Feature feature) override;

    /// True while any window currently has a blur region applied.
    bool isActive() const override;

    /// Effect-chain ordering. 20 sits between the standard blur slot
    /// and the post-window-decoration effects.
    int requestedEffectChainPosition() const override { return 20; }

    /// Intercepts ``DynamicPropertyChange`` on application QObjects so
    /// X11 ``_KDE_NET_WM_BLUR_BEHIND_REGION`` updates are picked up.
    bool eventFilter(QObject* watched, QEvent* event) override;

    /// False — we always composite via the GPU, never direct scanout.
    bool blocksDirectScanout() const override;

public Q_SLOTS:
    // Window / view bookkeeping (slots)

    /// Allocates per-window state and wires up the property / contrast
    /// signal forwarding. Called by EffectsHandler when a new window
    /// is shown.
    void slotWindowAdded(KWin::EffectWindow* w);

    /// Releases per-window state and disconnects all signals.
    void slotWindowDeleted(KWin::EffectWindow* w);

    /// Drops the per-view BlurRenderData when an output goes away,
    /// preventing dangling GLTexture handles.
    void slotViewRemoved(KWin::RenderView* view);

#if KWIN_BUILD_X11
    /// X11 path: pick up changes to the
    /// ``_KDE_NET_WM_BLUR_BEHIND_REGION`` property.
    void slotPropertyNotify(KWin::EffectWindow* w, long atom);
#endif

    /// Hook into the decoration so blurRegionChanged updates land in
    /// updateBlurRegion. Called from slotWindowAdded and whenever the
    /// decoration is swapped.
    void setupDecorationConnections(EffectWindow* w);

private:
    // Internals

    /// Build the lookup tables (iteration count, offset, expandSize)
    /// that translate BlurStrength 1..N into Kawase parameters.
    void initBlurStrengthValues();

    /// Computed blur region for the window content (client surface),
    /// taking into account the window's blur mask + KWin's contrast
    /// region.
    Region blurRegion(EffectWindow* w) const;

    /// Computed blur region for the server-side decoration (titlebar,
    /// shadow border, …) of ``w``.
    Region decorationBlurRegion(const EffectWindow* w) const;

    /// True if ``w`` has a KDecoration that opts into the blur-behind
    /// protocol — only then does the decoration get blurred.
    bool decorationSupportsBlurBehind(const EffectWindow* w) const;

    /// Master gate before launching the blur pipeline: not blurred if
    /// fully opaque, if the user's class whitelist excludes it, if blur
    /// region is empty, etc.
    bool shouldBlur(const EffectWindow* w, int mask, const WindowPaintData& data) const;

    /// Recompute and cache the blur region for ``w``. Called on
    /// window-added / decoration-swap / explicit property change.
    void updateBlurRegion(EffectWindow* w);

    /// Heart of the effect. Allocates / rebuilds per-view framebuffers,
    /// captures the background, runs the Dual Kawase chain (skipped at
    /// offset 0), uploads vertex data, and dispatches the final
    /// rounded-rect onscreen pass with all the SDF / drift / lens /
    /// rim uniforms set.
    void blur(const RenderTarget& renderTarget, const RenderViewport& viewport, EffectWindow* w, int mask, const Region& deviceRegion, WindowPaintData& data);

    /// Lazily generate the procedural noise texture used to grain the
    /// blurred output. Returns the cached texture on subsequent calls
    /// unless the configured noise strength changed.
    GLTexture* ensureNoiseTexture();

    /// Pure helper: combine saturation × contrast × brightness into one
    /// 4×4 colour matrix. Identity (an empty optional) when all three
    /// arguments equal 1.0.
    QMatrix4x4 colorMatrix(const float& brightness, const float& saturation, const float& contrast) const;

private:
    // Compiled shader passes

    /**
     * Final onscreen pass: reads framebuffers[0] (passthrough) or [1]
     * (blurred), applies the rounded-rect SDF, RGB drift,
     * magnify lens, rim highlight, then writes to the screen. Every
     * uniform location is cached at construction time so per-frame
     * setUniform calls don't have to hash the name.
     */
    struct
    {
        std::unique_ptr<GLShader> shader;
        int mvpMatrixLocation;
        int colorMatrixLocation;
        int offsetLocation;
        int halfpixelLocation;
        int boxLocation;
        int cornerRadiusLocation;
        int opacityLocation;

        int blurSizeLocation;
        int rgbDriftStrengthLocation;
        int magnifyGlassStrengthLocation;
        int refractionWidthLocation;
        int highlightWidthLocation;
        int highlightStrengthLocation;
        int blurTypeLocation;
    } m_roundedOnscreenPass;

    /// Dual Kawase downsample (halves resolution per iteration).
    struct
    {
        std::unique_ptr<GLShader> shader;
        int mvpMatrixLocation;
        int offsetLocation;
        int halfpixelLocation;
    } m_downsamplePass;

    /// Dual Kawase upsample (doubles resolution per iteration).
    struct
    {
        std::unique_ptr<GLShader> shader;
        int mvpMatrixLocation;
        int offsetLocation;
        int halfpixelLocation;
    } m_upsamplePass;

    /// Grain pass — multiplies the blurred result by a sparse white-
    /// noise texture so flat regions don't read as plastic-smooth.
    struct
    {
        std::unique_ptr<GLShader> shader;
        int mvpMatrixLocation;
        int noiseTextureSizeLocation;

        std::unique_ptr<GLTexture> noiseTexture;
        qreal noiseTextureScale = 1.0;
        int noiseTextureStength = 0;
    } m_noisePass;

    // Mutable state

    /// True once every shader pass loaded + validated. False keeps the
    /// effect inert (drawWindow falls through to the default opaque
    /// path).
    bool m_valid = false;

#if KWIN_BUILD_X11
    /// Interned atom for ``_KDE_NET_WM_BLUR_BEHIND_REGION``. Cached
    /// once at startup; -1 means uninitialised.
    long net_wm_blur_region = 0;
#endif

    Region m_paintedDeviceArea; ///< Accumulated painted area in the current frame, bottom-up.
    Region m_currentDeviceBlur; ///< Accumulated blurred area in the current frame, bottom-up.
    RenderView* m_currentView = nullptr; ///< View being painted right now (set by prePaintWindow).

    // kcfg-driven knobs (kept in sync by reconfigure)

    QMatrix4x4 m_colorMatrix; ///< Saturation × contrast × brightness for the onscreen pass.
    float m_rgbDriftStrength; ///< Chromatic-aberration band intensity at the rim.
    float m_magnifyGlassStrength; ///< Rim-only inward UV pull, simulates lens thickness.
    float m_refractionWidth; ///< Pixel width of the rim-concentrated effect band.
    float m_highlightWidth; ///< Pixel width of the bright glass rim.
    float m_highlightStrength; ///< Rim intensity multiplier.
    int m_blurType; ///< Final-pass kernel: 0=Gaussian, 1=Box, 2=Lens (bokeh).

    size_t m_iterationCount; ///< Number of Kawase halve/double passes (drives texture chain length).
    float m_offset; ///< Kawase tap offset; 0.0 means "no blur, passthrough".
    int m_expandSize; ///< Pixels of dirty-region expansion needed for taps near the rim.
    int m_noiseStrength; ///< 0..N grain intensity; 0 disables the noise pass entirely.

    QStringList m_windowClasses; ///< Window-class list for the blur-match filter.
    bool m_whitelist; ///< True: only blur listed classes. False: blur everything except listed.
    bool m_blurDecorations; ///< Apply blur under the server-side decoration too.

    // Per-strength lookup tables (populated by initBlurStrengthValues)

    /// Per-iteration Kawase tuning: at iteration ``i``, ``offset``
    /// ranges from minOffset..maxOffset and the region is expanded by
    /// ``expandSize`` pixels for tap safety.
    struct OffsetStruct
    {
        float minOffset;
        float maxOffset;
        int expandSize;
    };

    QList<OffsetStruct> blurOffsets;

    /// Decoded BlurStrength setting: ``iteration`` is how many Kawase
    /// passes to run, ``offset`` is the tap multiplier inside the
    /// downsample / upsample shader.
    struct BlurValuesStruct
    {
        int iteration;
        float offset;
    };

    QList<BlurValuesStruct> blurStrengthValues;

    // Per-window state + signal bookkeeping

    QMap<EffectWindow*, QMetaObject::Connection> windowBlurChangedConnections;
    QMap<EffectWindow*, QMetaObject::Connection> windowContrastChangedConnections;
    QMap<EffectWindow*, QMetaObject::Connection> windowFrameGeometryChangedConnections;
    std::unordered_map<EffectWindow*, BlurEffectData> m_windows;

    // Wayland protocol managers (lazy-removed on idle)

    /// Singleton blur-behind-region protocol handler. Created on first
    /// use, torn down after a settle delay so a no-blur window doesn't
    /// thrash the global.
    static BlurManagerInterface* s_blurManager;
    static QTimer* s_blurManagerRemoveTimer;

    /// Same idea for the contrast manager.
    static ContrastManagerInterface* s_contrastManager;
    static QTimer* s_contrastManagerRemoveTimer;
};

inline bool BlurEffect::provides(Effect::Feature feature)
{
    if (feature == Blur) {
        return true;
    }
    return KWin::Effect::provides(feature);
}

} // namespace KWin
