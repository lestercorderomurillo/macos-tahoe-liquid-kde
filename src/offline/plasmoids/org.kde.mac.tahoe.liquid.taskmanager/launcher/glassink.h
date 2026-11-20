// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QColor>
#include <QPointF>
#include <QSizeF>
#include <algorithm>
#include <cmath>

namespace GlassInk {
inline double luminance(const QColor &color)
{
    const auto linear = [](double x) { return x <= .04045 ? x / 12.92 : std::pow((x + .055) / 1.055, 2.4); };
    return .2126 * linear(color.redF()) + .7152 * linear(color.greenF()) + .0722 * linear(color.blueF());
}

inline QColor composite(const QColor &backdrop, const QColor &fill)
{
    const double a = fill.alphaF();
    return QColor::fromRgbF(backdrop.redF() * (1 - a) + fill.redF() * a,
                            backdrop.greenF() * (1 - a) + fill.greenF() * a,
                            backdrop.blueF() * (1 - a) + fill.blueF() * a);
}

inline double channel(double light)
{
    return light <= .0031308 ? light * 12.92 : 1.055 * std::pow(light, 1 / 2.4) - .055;
}

inline QColor foreground(QColor base, double local, double left, double right, double top, double bottom)
{
    const double nearby = (left + right + top + bottom) / 4;
    const double t = std::clamp((.65 * local + .35 * nearby - .09) / .22, 0., 1.);
    double ink = .98 - .92 * t * t * (3 - 2 * t);
    const double bg = local + .05;
    // Preserve contrast against the local surface, including its saved fill.
    if (1.05 / bg > bg / .05)
        ink = std::max(ink, channel(bg * 4.5 - .05));
    else
        ink = std::min(ink, channel(bg / 4.5 - .05));

    // At a hard edge the coarse compositor grid can place a short label
    // on either side. Balance its contrast against both observed extremes.
    const double low = std::min({local, left, right, top, bottom}) + .05;
    const double high = std::max({local, left, right, top, bottom}) + .05;
    const double edge = std::clamp((high / low - 4.5) / 5, 0., 1.);
    ink = std::clamp(ink + edge * (channel(std::sqrt(low * high) - .05) - ink), 0., 1.);
    return QColor::fromRgbF(ink, ink, ink, base.alphaF());
}

template <typename SurfaceAt>
QColor sample(QColor base, QPointF point, QSizeF radius, SurfaceAt surfaceAt)
{
    const auto light = [&](double dx, double dy) { return luminance(surfaceAt(point + QPointF(dx, dy))); };
    return foreground(base, light(0, 0), light(-radius.width(), 0), light(radius.width(), 0),
                      light(0, -radius.height()), light(0, radius.height()));
}
}
