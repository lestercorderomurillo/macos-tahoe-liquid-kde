/*
    SPDX-FileCopyrightText: 2008 Cédric Borgese <cedric.borgese@gmail.com>
    SPDX-FileCopyrightText: 2026 MacTahoe Liquid KDE contributors

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include "kwin_version_compat.h"

#include <QPointF>
#include <QRectF>

#include <array>
#include <chrono>

#if ACRYLIC_GLASS_KWIN_6_7
#include "effect/timeline.h"
#endif

namespace KWin {

#if ACRYLIC_GLASS_KWIN_6_7
class RenderView;
#endif

/**
 * The subset of Wobbly Windows settings that affects the spring mesh.
 *
 * Wobbly Windows exposes these through QObject properties. Reading them
 * from the loaded effect keeps the glass mesh in lockstep with custom
 * Wobbly settings without duplicating its KConfig schema.
 */
struct WobblyShapeParameters
{
    qreal stiffness = 0.15;
    qreal drag = 0.80;
    qreal moveFactor = 0.10;
    qreal minVelocity = 0.0;
    qreal maxVelocity = 1000.0;
    qreal stopVelocity = 0.5;
    qreal minAcceleration = 0.0;
    qreal maxAcceleration = 1000.0;
    qreal stopAcceleration = 0.5;
    int xTessellation = 20;
    int yTessellation = 20;
};

/**
 * A local mirror of Wobbly Windows' 4x4 spring mesh.
 *
 * KWin applies Wobbly's deformation to a temporary WindowQuadList and
 * discards it after painting the window. Acrylic Glass therefore has to
 * advance the same physical model to know where the glass surface will be.
 * The equations and ordering below intentionally mirror
 * src/plugins/wobblywindows/wobblywindows.cpp.
 */
class WobblyShape
{
public:
    enum class Status {
        Free,
        Moving,
    };

    WobblyShape(const WobblyShapeParameters& parameters, const QRectF& geometry, const QPointF& cursorPosition, bool resizing);

    /// Start another move/resize without discarding the existing spring
    /// state or clock. Wobbly does the same when a drag is restarted before
    /// the previous one has settled.
    void beginMovedResized(const QPointF& cursorPosition, const QRectF& geometry, bool resizing);

    void noteGeometryStep(const QRectF& geometry);
    void noteGeometryFinished(const QRectF& geometry);

    /// Advances in Wobbly's 10 ms integration slices. Returns false once
    /// the post-drag spring has settled and the effect released the window.
    bool advance(std::chrono::milliseconds delta, const QRectF& geometry);

    /// Maps normalized frame coordinates through the same cubic Bernstein
    /// surface used by Wobbly's WindowQuadList.
    QPointF map(qreal u, qreal v, const QRectF& geometry) const;

    /// Bounding rectangle for the current (possibly non-linear) surface.
    QRectF mappedBounds(const QRectF& geometry) const;

    int xTessellation() const
    {
        return m_parameters.xTessellation;
    }

    int yTessellation() const
    {
        return m_parameters.yTessellation;
    }

    bool isWobbling() const
    {
        return m_wobbling;
    }

private:
    struct Pair
    {
        qreal x = 0.0;
        qreal y = 0.0;
    };

    static Pair computeBezierPoint(const std::array<Pair, 16>& positions, qreal u, qreal v);
    static void fixVectorBounds(Pair& vector, qreal minimum, qreal maximum);
    static void heightRingLinearMean(std::array<Pair, 16>& data, std::array<Pair, 16>& buffer);
    void constrainPickedPoint(const QPointF& cursorPosition, const QRectF& geometry);
    bool update(const QRectF& geometry, qreal time);

    WobblyShapeParameters m_parameters;
    std::array<Pair, 16> m_origin;
    std::array<Pair, 16> m_position;
    std::array<Pair, 16> m_velocity;
    std::array<Pair, 16> m_acceleration;
    std::array<Pair, 16> m_buffer;
    std::array<bool, 16> m_constraint;

    Status m_status = Status::Moving;
    bool m_wobbling = false;
    bool m_canWobbleTop = false;
    bool m_canWobbleLeft = false;
    bool m_canWobbleRight = false;
    bool m_canWobbleBottom = false;
    QRectF m_resizeOriginalRect;
};

/**
 * Per-window clock wrapper. Wobbly 6.7+ derives frame deltas from the
 * RenderView's presentation timestamp; 6.6 receives the equivalent
 * timestamp in prePaintWindow().
 */
class WobblyShapeTracker
{
public:
    WobblyShapeTracker(const WobblyShapeParameters& parameters, const QRectF& geometry, const QPointF& cursorPosition, bool resizing);

    void beginMovedResized(const QPointF& cursorPosition, const QRectF& geometry, bool resizing);

#if ACRYLIC_GLASS_KWIN_6_7
    bool advance(const RenderView* view, const QRectF& geometry);
#else
    bool advance(std::chrono::milliseconds presentTime, const QRectF& geometry);
#endif

    WobblyShape& shape()
    {
        return m_shape;
    }

    const WobblyShape& shape() const
    {
        return m_shape;
    }

    /// True after the shape has reported its final settled frame. The
    /// tracker is retained for that frame so a 6.6 transformed window still
    /// gets glass; it is removed on the next advance.
    bool retirePending() const
    {
        return m_retirePending;
    }

private:
    WobblyShape m_shape;
    bool m_retirePending = false;
#if ACRYLIC_GLASS_KWIN_6_7
    AnimationClock m_clock;
#else
    std::chrono::milliseconds m_clock;
#endif
};

} // namespace KWin
