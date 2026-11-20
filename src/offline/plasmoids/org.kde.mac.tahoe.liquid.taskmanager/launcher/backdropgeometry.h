// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QWindow>

namespace BackdropGeometry
{
// A drag can leave the origin between logical pixels even on a 2x output.
// Outward alignment can then add a pixel to an otherwise exact client size.
inline int edgeTolerance(const QWindow &window)
{
    const qreal scale = window.devicePixelRatio();
    return qFuzzyCompare(scale, qreal(qRound(scale))) && scale <= 1 ? 0 : 1;
}

inline bool sizeMatches(const QRect &frame, const QWindow &window)
{
    const qreal scale = window.devicePixelRatio();
    const int extra = qFuzzyCompare(scale, qreal(qRound(scale))) ? 1 : 2;
    const QSize delta = frame.size() - window.size();
    return delta.width() >= 0 && delta.width() <= extra
        && delta.height() >= 0 && delta.height() <= extra;
}
}
