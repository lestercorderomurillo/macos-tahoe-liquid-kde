// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QWindow>

namespace BackdropGeometry
{
// KWin sends an outward-aligned logical frame. On a fractional output each
// edge can contribute a pixel beyond the client window's integer dimensions.
inline int edgeTolerance(const QWindow &window)
{
    const qreal scale = window.devicePixelRatio();
    return qFuzzyCompare(scale, qreal(qRound(scale))) ? 0 : 1;
}

inline bool sizeMatches(const QRect &frame, const QWindow &window)
{
    const int extra = 2 * edgeTolerance(window);
    const QSize delta = frame.size() - window.size();
    return delta.width() >= 0 && delta.width() <= extra
        && delta.height() >= 0 && delta.height() <= extra;
}
}
