// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QColor>
#include <QPointF>
#include <QList>
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

inline bool isLightInk(double luminance)
{
    return luminance > std::sqrt(.05 * 1.05) - .05;
}

enum class Family { Dark, Light };

inline Family familyOf(QColor color)
{
    return isLightInk(luminance(color)) ? Family::Light : Family::Dark;
}

// The component profile measures the common material. The smaller profiles
// measure the backdrop behind individual glyphs, labels and category pills.
struct Profile {
    int columns = 3;
    int rows = 3;
    double crossCenterWeight = 0.;
};
inline constexpr Profile component{9, 5};
inline constexpr Profile control{3, 3, .65};
inline constexpr Profile label{5, 3};
inline constexpr Profile categoryRow{5, 1};

// CIE L* on a 0..1 scale. A separation of .20 is twenty lightness points.
inline double lightness(QColor color)
{
    const double y = luminance(color);
    return y <= 216. / 24389. ? y * (24389. / 2700.) : 1.16 * std::cbrt(y) - .16;
}

class Samples {
public:
    void add(const QColor &surface, double weight = 1.)
    {
        if (!(weight > 0.) || !surface.isValid() || !surface.alpha()) return;
        // Adjacent sample points often fall in the same compositor grid cell.
        for (const auto &sample : m_samples)
            if (sample.color == surface) return;
        m_samples.append(Sample{surface, lightness(surface)});
    }

    QColor tone(QColor base) const
    {
        if (m_samples.isEmpty() || !base.isValid() || !base.alpha()) return base;
        constexpr double minimum = .20;
        constexpr int maximumShift = 51; // At most one fifth of the encoded channel range.
        double best = separation(base);
        if (best >= minimum) return base;
        QColor result = base;
        const Family family = familyOf(base);
        for (int step = 1; step <= maximumShift; ++step) {
            for (int direction : {-1, 1}) {
                const double delta = direction * step / 255.;
                const auto shift = [delta](double channel) { return std::clamp(channel + delta, 0., 1.); };
                const QColor candidate = QColor::fromRgbF(shift(base.redF()), shift(base.greenF()),
                                                          shift(base.blueF()), base.alphaF());
                if (familyOf(candidate) != family) continue;
                const double distance = separation(candidate);
                if (distance >= minimum) return candidate;
                if (distance > best) {
                    result = candidate;
                    best = distance;
                }
            }
        }
        return result;
    }

private:
    struct Sample { QColor color; double lightness; };
    QList<Sample> m_samples;

    double separation(QColor ink) const
    {
        double worst = 1.;
        const double opaque = lightness(ink);
        for (const auto &sample : m_samples) {
            const double visible = ink.alphaF() == 1. ? opaque : lightness(composite(sample.color, ink));
            worst = std::min(worst, std::abs(visible - sample.lightness));
        }
        return worst;
    }
};

template <typename Visit>
void forEachPoint(const Profile &profile, QPointF center, QSizeF radius, Visit visit)
{
    const auto offset = [](int i, int count) { return count > 1 ? 2. * i / (count - 1) - 1. : 0.; };
    for (int y = 0; y < profile.rows; ++y) {
        for (int x = 0; x < profile.columns; ++x) {
            double weight = 1.;
            if (profile.crossCenterWeight > 0.) {
                const bool centerX = x == profile.columns / 2;
                const bool centerY = y == profile.rows / 2;
                if (!centerX && !centerY) continue;
                weight = centerX && centerY ? profile.crossCenterWeight
                    : (1. - profile.crossCenterWeight) / (profile.columns + profile.rows - 2);
            }
            const QPointF delta(offset(x, profile.columns) * radius.width(), offset(y, profile.rows) * radius.height());
            visit(center + delta, weight);
        }
    }
}

template <typename SurfaceAt>
Samples sample(const Profile &profile, QPointF center, QSizeF radius, SurfaceAt surfaceAt)
{
    Samples samples;
    forEachPoint(profile, center, radius, [&](QPointF point, double weight) { samples.add(surfaceAt(point), weight); });
    return samples;
}
}
