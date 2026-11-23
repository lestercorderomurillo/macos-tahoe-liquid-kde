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

// Sample geometry is in logical pixels. Agreement and contrast are independent
// of the number of samples, including a group of partially visible labels.
struct Profile {
    int columns = 3;
    int rows = 3;
    double contrast = 5.2;
    double advantage = 1.;
    double enter = .5;
    double retain = .5;
    bool preserveTheme = false;
    // A centered control reads a cross through its glyph; labels vote over their extent.
    double crossCenterWeight = 0.;
};
inline constexpr Profile control{.crossCenterWeight = .65};
inline constexpr Profile menu{.columns = 5, .advantage = 1.25};
inline constexpr Profile label{.columns = 5, .advantage = 1.25, .enter = .8, .preserveTheme = true};
inline constexpr Profile categoryRow{.columns = 5, .rows = 1, .advantage = 1.25, .enter = .8, .retain = .55, .preserveTheme = true};

inline QColor neutralInk(QColor base, double surface, bool light, double contrast)
{
    const double luminance = light
        ? std::clamp((surface + .05) * contrast - .05, .55, 1.)
        : std::max(0., (surface + .05) / contrast - .05);
    const double gray = luminance <= .0031308
        ? 12.92 * luminance : 1.055 * std::pow(luminance, 1. / 2.4) - .055;
    return QColor::fromRgbF(gray, gray, gray, base.alphaF());
}

class Samples {
public:
    Samples(QColor base, const Profile &profile)
        : m_base(base), m_profile(profile), m_light(isLightInk(luminance(base))),
          m_preferred(profile.preserveTheme ? luminance(base) : double(m_light)),
          m_limit(m_light ? 1. : 0.)
    {}

    void add(const QColor &surface, double weight = 1.)
    {
        // Unsupported wallpaper margins provide no evidence for switching ink.
        m_requestedWeight += weight;
        if (!surface.isValid() || !surface.alpha()) return;
        const double lightness = luminance(surface);
        m_sum += weight * lightness;
        m_count += weight;
        const double preferred = contrastRatio(m_preferred, lightness);
        const double alternate = contrastRatio(m_light ? 0. : 1., lightness);
        if (alternate >= m_profile.advantage * preferred
            && (!m_profile.preserveTheme || (preferred < 4.5 && alternate >= 4.5))) {
            m_limit = m_light ? std::min(m_limit, lightness) : std::max(m_limit, lightness);
            m_votes += weight;
        }
    }

    QColor resolve(QColor previous) const
    {
        if (!m_count) return m_base;
        const double mean = m_sum / m_count;
        if (m_profile.crossCenterWeight > 0.)
            return neutralInk(m_base, mean, !isLightInk(mean), m_profile.contrast);
        const bool wasAlternate = isLightInk(luminance(previous)) != m_light;
        const bool alternate = m_votes >= m_requestedWeight * (wasAlternate ? m_profile.retain : m_profile.enter);
        if (m_profile.preserveTheme && !alternate) return m_base;
        const double surface = m_profile.preserveTheme ? m_limit : mean;
        return neutralInk(m_base, surface, alternate != m_light, m_profile.contrast);
    }

private:
    QColor m_base;
    Profile m_profile;
    bool m_light;
    double m_preferred;
    double m_limit;
    double m_sum = 0.;
    double m_count = 0.;
    double m_votes = 0.;
    double m_requestedWeight = 0.;
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
QColor sample(QColor base, QColor previous, const Profile &profile, QPointF center, QSizeF radius, SurfaceAt surfaceAt)
{
    Samples samples(base, profile);
    forEachPoint(profile, center, radius, [&](QPointF point, double weight) { samples.add(surfaceAt(point), weight); });
    return samples.resolve(previous);
}
}
