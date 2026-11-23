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

inline double contrastRatio(double ink, double surface)
{
    return (std::max(ink, surface) + .05) / (std::min(ink, surface) + .05);
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

class Samples {
public:
    void add(const QColor &surface, double weight = 1.)
    {
        if (!(weight > 0.) || !std::isfinite(weight)) return;
        if (!surface.isValid() || !surface.alpha()) return;
        m_luminance += weight * luminance(surface);
        m_weight += weight;
    }

    QColor tone(QColor base) const
    {
        if (!m_weight || !base.isValid() || !base.alpha()) return base;
        const double surface = m_luminance / m_weight;
        const double original = contrastRatio(luminance(base), surface);
        const auto family = familyOf(base);
        const double endpoint = family == Family::Light ? 0. : 1.;
        const double need = std::clamp((3. - original) / 2., 0., 1.);
        const double amount = .20 * need * need * (3. - 2. * need);
        const QColor tone = QColor::fromRgbF(std::lerp(base.redF(), endpoint, amount),
                                             std::lerp(base.greenF(), endpoint, amount),
                                             std::lerp(base.blueF(), endpoint, amount),
                                             base.alphaF());
        return familyOf(tone) == family && contrastRatio(luminance(tone), surface) > original
            ? tone : base;
    }

private:
    double m_weight = 0.;
    double m_luminance = 0.;
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
