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
inline constexpr Profile menu{5, 3};
inline constexpr Profile label{5, 3};
inline constexpr Profile categoryRow{5, 1};
inline constexpr double targetContrast = 5.2;

class Samples {
public:
    void add(const QColor &surface, double weight = 1.)
    {
        if (!(weight > 0.) || !std::isfinite(weight)) return;
        m_requested += weight;
        if (!surface.isValid() || !surface.alpha()) return;
        const double lightness = luminance(surface);
        m_luminance += weight * lightness;
        m_weight += weight;
        // Once text is readable, extra contrast in an already favourable
        // region should not outweigh unreadable text elsewhere in the surface.
        m_darkScore += weight * std::min(targetContrast, contrastRatio(0., lightness));
        m_lightScore += weight * std::min(targetContrast, contrastRatio(1., lightness));
    }

    Family family(QColor preferred, double tolerance = 1.10) const
    {
        // Wallpaper plugins can expose unsampled margins around a centered image.
        if (m_weight < .5 * m_requested) return familyOf(preferred);
        if (m_darkScore > tolerance * m_lightScore) return Family::Dark;
        if (m_lightScore > tolerance * m_darkScore) return Family::Light;
        return familyOf(preferred);
    }

    QColor tone(QColor base, Family family, double contrast = targetContrast) const
    {
        if (!m_weight) return familyOf(base) == family ? base
            : QColor::fromRgbF(family == Family::Light, family == Family::Light, family == Family::Light, base.alphaF());
        const double surface = m_luminance / m_weight;
        const bool light = family == Family::Light;
        const double extreme = light ? 1. : 0.;
        const double grayLimit = light ? .55 : .155;
        const double ideal = light ? (surface + .05) * contrast - .05 : (surface + .05) / contrast - .05;
        double ink = std::clamp(ideal, std::min(extreme, grayLimit), std::max(extreme, grayLimit));

        // On a patch as bright as white ink (or as dark as black ink), the gray
        // end of the same family is more legible. Ease through that end of the
        // range in proportion to its contrast gain, without a polarity switch.
        const double gain = contrastRatio(grayLimit, surface) / contrastRatio(ink, surface);
        const double t = std::clamp((gain - 1.) / (contrastRatio(extreme, grayLimit) - 1.), 0., 1.);
        ink = std::lerp(ink, grayLimit, t * t * (3. - 2. * t));
        const double gray = ink <= .0031308 ? 12.92 * ink : 1.055 * std::pow(ink, 1. / 2.4) - .055;
        return QColor::fromRgbF(gray, gray, gray, base.alphaF());
    }

private:
    double m_requested = 0.;
    double m_weight = 0.;
    double m_luminance = 0.;
    double m_darkScore = 0.;
    double m_lightScore = 0.;
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
