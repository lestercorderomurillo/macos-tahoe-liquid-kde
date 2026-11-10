/*
    SPDX-FileCopyrightText: 2008 Cédric Borgese <cedric.borgese@gmail.com>
    SPDX-FileCopyrightText: 2026 MacTahoe Liquid KDE contributors

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "wobbly_shape.h"

#include <algorithm>
#include <cmath>
#include <initializer_list>
#include <limits>

namespace KWin {

namespace {

constexpr auto s_integrationStep = std::chrono::milliseconds(10);

} // namespace

WobblyShape::WobblyShape(const WobblyShapeParameters& parameters, const QRectF& geometry, const QPointF& cursorPosition, bool resizing)
    : m_parameters(parameters)
    , m_resizeOriginalRect(geometry)
{
    m_parameters.xTessellation = std::max(1, m_parameters.xTessellation);
    m_parameters.yTessellation = std::max(1, m_parameters.yTessellation);

    const qreal x = geometry.x();
    const qreal y = geometry.y();
    const qreal width = geometry.width();
    const qreal height = geometry.height();
    const qreal xIncrement = width / 3.0;
    const qreal yIncrement = height / 3.0;

    Pair initValue{x, y};
    for (unsigned int row = 0; row < 4; ++row) {
        for (unsigned int column = 0; column < 4; ++column) {
            const unsigned int index = row * 4 + column;
            m_origin[index] = initValue;
            m_position[index] = initValue;
            m_velocity[index] = {};
            m_acceleration[index] = {};
            m_buffer[index] = {};
            m_constraint[index] = false;

            if (column != 2) {
                initValue.x += xIncrement;
            } else {
                initValue.x = x + width;
            }
        }
        initValue.x = x;
        if (row != 2) {
            initValue.y += yIncrement;
        } else {
            initValue.y = y + height;
        }
    }

    beginMovedResized(cursorPosition, geometry, resizing);
}

void WobblyShape::beginMovedResized(const QPointF& cursorPosition, const QRectF& geometry, bool resizing)
{
    m_status = Status::Moving;
    constrainPickedPoint(cursorPosition, geometry);

    if (resizing) {
        // On a resize, do not allow any edge to wobble until it has moved
        // away from the geometry captured at the start of this resize.
        m_canWobbleTop = false;
        m_canWobbleLeft = false;
        m_canWobbleRight = false;
        m_canWobbleBottom = false;
        m_resizeOriginalRect = geometry;
    } else {
        m_canWobbleTop = true;
        m_canWobbleLeft = true;
        m_canWobbleRight = true;
        m_canWobbleBottom = true;
    }
}

void WobblyShape::constrainPickedPoint(const QPointF& cursorPosition, const QRectF& geometry)
{
    const qreal xIncrement = geometry.width() / 3.0;
    const qreal yIncrement = geometry.height() / 3.0;
    const qreal pickedX = (cursorPosition.x() - geometry.x()) / xIncrement + 0.5;
    const qreal pickedY = (cursorPosition.y() - geometry.y()) / yIncrement + 0.5;
    int pickedColumn = std::isfinite(pickedX) ? static_cast<int>(pickedX) : 0;
    int pickedRow = std::isfinite(pickedY) ? static_cast<int>(pickedY) : 0;
    pickedColumn = std::clamp(pickedColumn, 0, 3);
    pickedRow = std::clamp(pickedRow, 0, 3);
    m_constraint[pickedRow * 4 + pickedColumn] = true;
}

void WobblyShape::noteGeometryStep(const QRectF& geometry)
{
    if (geometry.y() != m_resizeOriginalRect.y()) {
        m_canWobbleTop = true;
    }
    if (geometry.x() != m_resizeOriginalRect.x()) {
        m_canWobbleLeft = true;
    }
    if (geometry.right() != m_resizeOriginalRect.right()) {
        m_canWobbleRight = true;
    }
    if (geometry.bottom() != m_resizeOriginalRect.bottom()) {
        m_canWobbleBottom = true;
    }
}

void WobblyShape::noteGeometryFinished(const QRectF& geometry)
{
    m_status = Status::Free;
    noteGeometryStep(geometry);
}

bool WobblyShape::advance(std::chrono::milliseconds delta, const QRectF& geometry)
{
    while (delta.count() > 0) {
        const auto step = std::min(delta, s_integrationStep);
        delta -= step;
        if (!update(geometry, step.count())) {
            return false;
        }
    }
    return true;
}

QPointF WobblyShape::map(qreal u, qreal v, const QRectF& geometry) const
{
    const QPointF flatPoint(geometry.x() + u * geometry.width(), geometry.y() + v * geometry.height());
    if (!m_wobbling) {
        return flatPoint;
    }

    const Pair mapped = computeBezierPoint(m_position, u, v);
    return QPointF(mapped.x, mapped.y);
}

QRectF WobblyShape::mappedBounds(const QRectF& geometry) const
{
    if (!m_wobbling) {
        return geometry;
    }

    qreal left = std::numeric_limits<qreal>::max();
    qreal top = std::numeric_limits<qreal>::max();
    qreal right = std::numeric_limits<qreal>::lowest();
    qreal bottom = std::numeric_limits<qreal>::lowest();
    for (const Pair& point : m_position) {
        left = std::min(left, point.x);
        top = std::min(top, point.y);
        right = std::max(right, point.x);
        bottom = std::max(bottom, point.y);
    }
    return QRectF(QPointF(left, top), QPointF(right, bottom));
}

WobblyShape::Pair WobblyShape::computeBezierPoint(const std::array<Pair, 16>& positions, qreal u, qreal v)
{
    const qreal px[4] = {
        (1 - u) * (1 - u) * (1 - u),
        3 * (1 - u) * (1 - u) * u,
        3 * (1 - u) * u * u,
        u * u * u,
    };
    const qreal py[4] = {
        (1 - v) * (1 - v) * (1 - v),
        3 * (1 - v) * (1 - v) * v,
        3 * (1 - v) * v * v,
        v * v * v,
    };

    Pair result;
    for (unsigned int row = 0; row < 4; ++row) {
        for (unsigned int column = 0; column < 4; ++column) {
            const Pair& point = positions[column + row * 4];
            result.x += px[column] * py[row] * point.x;
            result.y += px[column] * py[row] * point.y;
        }
    }
    return result;
}

bool WobblyShape::update(const QRectF& geometry, qreal time)
{
    const qreal xLength = geometry.width() / 3.0;
    const qreal yLength = geometry.height() / 3.0;

    Pair origin{geometry.x(), geometry.y()};
    for (unsigned int row = 0; row < 4; ++row) {
        for (unsigned int column = 0; column < 4; ++column) {
            m_origin[row * 4 + column] = origin;
            if (column != 2) {
                origin.x += xLength;
            } else {
                origin.x = geometry.x() + geometry.width();
            }
        }
        origin.x = geometry.x();
        if (row != 2) {
            origin.y += yLength;
        } else {
            origin.y = geometry.y() + geometry.height();
        }
    }

    Pair neighbors[4];
    Pair acceleration;
    qreal accelerationSum = 0.0;
    qreal velocitySum = 0.0;

    const auto constrainedAcceleration = [this](unsigned int index) {
        const Pair delta{
            m_origin[index].x - m_position[index].x,
            m_origin[index].y - m_position[index].y,
        };
        return Pair{
            delta.x * m_parameters.stiffness,
            delta.y * m_parameters.stiffness,
        };
    };

    if (m_constraint[0]) {
        m_acceleration[0] = constrainedAcceleration(0);
    } else {
        const Pair& position = m_position[0];
        neighbors[0] = m_position[1];
        neighbors[1] = m_position[4];
        acceleration.x = ((neighbors[0].x - position.x) - xLength) * m_parameters.stiffness + (neighbors[1].x - position.x) * m_parameters.stiffness;
        acceleration.y = ((neighbors[1].y - position.y) - yLength) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness;
        acceleration.x /= 2;
        acceleration.y /= 2;
        m_acceleration[0] = acceleration;
    }

    if (m_constraint[3]) {
        m_acceleration[3] = constrainedAcceleration(3);
    } else {
        const Pair& position = m_position[3];
        neighbors[0] = m_position[2];
        neighbors[1] = m_position[7];
        acceleration.x = (xLength - (position.x - neighbors[0].x)) * m_parameters.stiffness + (neighbors[1].x - position.x) * m_parameters.stiffness;
        acceleration.y = ((neighbors[1].y - position.y) - yLength) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness;
        acceleration.x /= 2;
        acceleration.y /= 2;
        m_acceleration[3] = acceleration;
    }

    if (m_constraint[12]) {
        m_acceleration[12] = constrainedAcceleration(12);
    } else {
        const Pair& position = m_position[12];
        neighbors[0] = m_position[13];
        neighbors[1] = m_position[8];
        acceleration.x = ((neighbors[0].x - position.x) - xLength) * m_parameters.stiffness + (neighbors[1].x - position.x) * m_parameters.stiffness;
        acceleration.y = (yLength - (position.y - neighbors[1].y)) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness;
        acceleration.x /= 2;
        acceleration.y /= 2;
        m_acceleration[12] = acceleration;
    }

    if (m_constraint[15]) {
        m_acceleration[15] = constrainedAcceleration(15);
    } else {
        const Pair& position = m_position[15];
        neighbors[0] = m_position[14];
        neighbors[1] = m_position[11];
        acceleration.x = (xLength - (position.x - neighbors[0].x)) * m_parameters.stiffness + (neighbors[1].x - position.x) * m_parameters.stiffness;
        acceleration.y = (yLength - (position.y - neighbors[1].y)) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness;
        acceleration.x /= 2;
        acceleration.y /= 2;
        m_acceleration[15] = acceleration;
    }

    for (unsigned int column = 1; column < 3; ++column) {
        if (m_constraint[column]) {
            m_acceleration[column] = constrainedAcceleration(column);
        } else {
            const Pair& position = m_position[column];
            neighbors[0] = m_position[column - 1];
            neighbors[1] = m_position[column + 1];
            neighbors[2] = m_position[column + 4];
            acceleration.x = (xLength - (position.x - neighbors[0].x)) * m_parameters.stiffness + ((neighbors[1].x - position.x) - xLength) * m_parameters.stiffness + (neighbors[2].x - position.x) * m_parameters.stiffness;
            acceleration.y = ((neighbors[2].y - position.y) - yLength) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness + (neighbors[1].y - position.y) * m_parameters.stiffness;
            acceleration.x /= 3;
            acceleration.y /= 3;
            m_acceleration[column] = acceleration;
        }
    }

    for (unsigned int column = 13; column < 15; ++column) {
        if (m_constraint[column]) {
            m_acceleration[column] = constrainedAcceleration(column);
        } else {
            const Pair& position = m_position[column];
            neighbors[0] = m_position[column - 1];
            neighbors[1] = m_position[column + 1];
            neighbors[2] = m_position[column - 4];
            acceleration.x = (xLength - (position.x - neighbors[0].x)) * m_parameters.stiffness + ((neighbors[1].x - position.x) - xLength) * m_parameters.stiffness + (neighbors[2].x - position.x) * m_parameters.stiffness;
            acceleration.y = (yLength - (position.y - neighbors[2].y)) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness + (neighbors[1].y - position.y) * m_parameters.stiffness;
            acceleration.x /= 3;
            acceleration.y /= 3;
            m_acceleration[column] = acceleration;
        }
    }

    for (unsigned int row = 1; row < 3; ++row) {
        const unsigned int index = row * 4;
        if (m_constraint[index]) {
            m_acceleration[index] = constrainedAcceleration(index);
        } else {
            const Pair& position = m_position[index];
            neighbors[0] = m_position[index + 1];
            neighbors[1] = m_position[index - 4];
            neighbors[2] = m_position[index + 4];
            acceleration.x = ((neighbors[0].x - position.x) - xLength) * m_parameters.stiffness + (neighbors[1].x - position.x) * m_parameters.stiffness + (neighbors[2].x - position.x) * m_parameters.stiffness;
            acceleration.y = (yLength - (position.y - neighbors[1].y)) * m_parameters.stiffness + ((neighbors[2].y - position.y) - yLength) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness;
            acceleration.x /= 3;
            acceleration.y /= 3;
            m_acceleration[index] = acceleration;
        }
    }

    for (unsigned int row = 1; row < 3; ++row) {
        const unsigned int index = row * 4 + 3;
        if (m_constraint[index]) {
            m_acceleration[index] = constrainedAcceleration(index);
        } else {
            const Pair& position = m_position[index];
            neighbors[0] = m_position[index - 1];
            neighbors[1] = m_position[index - 4];
            neighbors[2] = m_position[index + 4];
            acceleration.x = (xLength - (position.x - neighbors[0].x)) * m_parameters.stiffness + (neighbors[1].x - position.x) * m_parameters.stiffness + (neighbors[2].x - position.x) * m_parameters.stiffness;
            acceleration.y = (yLength - (position.y - neighbors[1].y)) * m_parameters.stiffness + ((neighbors[2].y - position.y) - yLength) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness;
            acceleration.x /= 3;
            acceleration.y /= 3;
            m_acceleration[index] = acceleration;
        }
    }

    for (unsigned int row = 1; row < 3; ++row) {
        for (unsigned int column = 1; column < 3; ++column) {
            const unsigned int index = row * 4 + column;
            if (m_constraint[index]) {
                m_acceleration[index] = constrainedAcceleration(index);
            } else {
                const Pair& position = m_position[index];
                neighbors[0] = m_position[index - 1];
                neighbors[1] = m_position[index + 1];
                neighbors[2] = m_position[index - 4];
                neighbors[3] = m_position[index + 4];
                acceleration.x = ((neighbors[0].x - position.x) - xLength) * m_parameters.stiffness + (xLength - (position.x - neighbors[1].x)) * m_parameters.stiffness + (neighbors[2].x - position.x) * m_parameters.stiffness + (neighbors[3].x - position.x) * m_parameters.stiffness;
                acceleration.y = (yLength - (position.y - neighbors[2].y)) * m_parameters.stiffness + ((neighbors[3].y - position.y) - yLength) * m_parameters.stiffness + (neighbors[0].y - position.y) * m_parameters.stiffness + (neighbors[1].y - position.y) * m_parameters.stiffness;
                acceleration.x /= 4;
                acceleration.y /= 4;
                m_acceleration[index] = acceleration;
            }
        }
    }

    heightRingLinearMean(m_acceleration, m_buffer);

    for (unsigned int index = 0; index < 16; ++index) {
        Pair accelerationValue = m_acceleration[index];
        fixVectorBounds(accelerationValue, m_parameters.minAcceleration, m_parameters.maxAcceleration);

        Pair& velocity = m_velocity[index];
        velocity.x = accelerationValue.x * time + velocity.x * m_parameters.drag;
        velocity.y = accelerationValue.y * time + velocity.y * m_parameters.drag;
        accelerationSum += std::abs(accelerationValue.x) + std::abs(accelerationValue.y);
    }

    heightRingLinearMean(m_velocity, m_buffer);

    for (unsigned int index = 0; index < 16; ++index) {
        Pair& position = m_position[index];
        Pair& velocity = m_velocity[index];
        fixVectorBounds(velocity, m_parameters.minVelocity, m_parameters.maxVelocity);
        position.x += velocity.x * time * m_parameters.moveFactor;
        position.y += velocity.y * time * m_parameters.moveFactor;
        velocitySum += std::abs(velocity.x) + std::abs(velocity.y);
    }

    if (!m_canWobbleTop) {
        for (unsigned int column = 0; column < 4; ++column) {
            for (unsigned int row = 0; row < 3; ++row) {
                m_position[column + row * 4].y = m_origin[column + row * 4].y;
            }
        }
    }
    if (!m_canWobbleBottom) {
        for (unsigned int column = 12; column < 16; ++column) {
            for (unsigned int row = 0; row < 3; ++row) {
                m_position[column - row * 4].y = m_origin[column - row * 4].y;
            }
        }
    }
    if (!m_canWobbleLeft) {
        for (unsigned int row = 0; row < 4; ++row) {
            for (unsigned int column = 0; column < 3; ++column) {
                m_position[row * 4 + column].x = m_origin[row * 4 + column].x;
            }
        }
    }
    if (!m_canWobbleRight) {
        for (unsigned int row = 0; row < 4; ++row) {
            for (unsigned int column = 0; column < 3; ++column) {
                const unsigned int index = row * 4 + 3 - column;
                m_position[index].x = m_origin[index].x;
            }
        }
    }

    m_wobbling = !(accelerationSum < m_parameters.stopAcceleration && velocitySum < m_parameters.stopVelocity);
    if (m_status != Status::Moving && !m_wobbling) {
        return false;
    }
    return true;
}

void WobblyShape::heightRingLinearMean(std::array<Pair, 16>& data, std::array<Pair, 16>& buffer)
{
    const auto average = [&](std::initializer_list<unsigned int> neighbors, unsigned int center, qreal divisor) {
        Pair result;
        for (const unsigned int index : neighbors) {
            result.x += data[index].x;
            result.y += data[index].y;
        }
        const qreal centerWeight = divisor - static_cast<qreal>(neighbors.size());
        result.x = (result.x + centerWeight * data[center].x) / divisor;
        result.y = (result.y + centerWeight * data[center].y) / divisor;
        return result;
    };

    buffer[0] = average({1, 4, 5}, 0, 6.0);
    buffer[3] = average({2, 7, 6}, 3, 6.0);
    buffer[12] = average({13, 8, 9}, 12, 6.0);
    buffer[15] = average({14, 11, 10}, 15, 6.0);
    buffer[1] = average({0, 2, 4, 5, 6}, 1, 10.0);
    buffer[2] = average({1, 3, 5, 6, 7}, 2, 10.0);
    buffer[13] = average({12, 14, 8, 9, 10}, 13, 10.0);
    buffer[14] = average({13, 15, 9, 10, 11}, 14, 10.0);
    buffer[4] = average({5, 0, 8, 1, 9}, 4, 10.0);
    buffer[8] = average({9, 4, 12, 5, 13}, 8, 10.0);
    buffer[7] = average({6, 3, 11, 2, 10}, 7, 10.0);
    buffer[11] = average({10, 7, 15, 6, 14}, 11, 10.0);

    for (unsigned int row = 1; row < 3; ++row) {
        for (unsigned int column = 1; column < 3; ++column) {
            const unsigned int index = row * 4 + column;
            buffer[index] = average({index - 1, index + 1, index - 4, index + 4,
                                        index - 5, index - 3, index + 3, index + 5},
                index, 16.0);
        }
    }

    data.swap(buffer);
}

void WobblyShape::fixVectorBounds(Pair& vector, qreal minimum, qreal maximum)
{
    if (std::abs(vector.x) < minimum) {
        vector.x = 0.0;
    } else if (std::abs(vector.x) > maximum) {
        vector.x = vector.x > 0.0 ? maximum : -maximum;
    }

    if (std::abs(vector.y) < minimum) {
        vector.y = 0.0;
    } else if (std::abs(vector.y) > maximum) {
        vector.y = vector.y > 0.0 ? maximum : -maximum;
    }
}

WobblyShapeTracker::WobblyShapeTracker(const WobblyShapeParameters& parameters, const QRectF& geometry, const QPointF& cursorPosition, bool resizing)
    : m_shape(parameters, geometry, cursorPosition, resizing)
#if !ACRYLIC_GLASS_KWIN_6_7
    , m_clock(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()))
#endif
{
}

void WobblyShapeTracker::beginMovedResized(const QPointF& cursorPosition, const QRectF& geometry, bool resizing)
{
    m_retirePending = false;
    m_shape.beginMovedResized(cursorPosition, geometry, resizing);
}

#if ACRYLIC_GLASS_KWIN_6_7
bool WobblyShapeTracker::advance(const RenderView* view, const QRectF& geometry)
{
    if (m_retirePending) {
        return false;
    }
    if (!view) {
        return true;
    }
    if (!m_shape.advance(m_clock.tick(view), geometry)) {
        // Wobbly removes the model on this frame. Keep the flat final mesh
        // available for one draw so 6.6's already-set transformed flag does
        // not make the glass disappear before the content becomes flat.
        m_retirePending = true;
    }
    return true;
}
#else
bool WobblyShapeTracker::advance(std::chrono::milliseconds presentTime, const QRectF& geometry)
{
    if (m_retirePending) {
        return false;
    }
    const auto delta = presentTime - m_clock;
    if (delta.count() <= 0) {
        return true;
    }
    m_clock = presentTime;
    if (!m_shape.advance(delta, geometry)) {
        m_retirePending = true;
    }
    return true;
}
#endif

} // namespace KWin
