// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QColor>
#include <QHash>
#include <QObject>
#include <QPointF>
#include <QList>
#include <QRectF>
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

// CIE L* on a 0..1 scale. A separation of .33 is thirty-three lightness points.
inline double lightnessFromLuminance(double y)
{
    return y <= 216. / 24389. ? y * (24389. / 2700.) : 1.16 * std::cbrt(y) - .16;
}

inline double lightness(QColor color)
{
    return lightnessFromLuminance(luminance(color));
}

inline QColor applyRoleCorrection(QColor base, QColor reference, QColor corrected)
{
    if (reference == corrected || !base.isValid() || !base.alpha()) return base;
    const auto adjust = [](double role, double before, double after) {
        return std::clamp(role + after - before, 0., 1.);
    };
    return QColor::fromRgbF(adjust(base.redF(), reference.redF(), corrected.redF()),
                            adjust(base.greenF(), reference.greenF(), corrected.greenF()),
                            adjust(base.blueF(), reference.blueF(), corrected.blueF()), base.alphaF());
}

enum class Correction { Shift, Flip };

struct CorrectionSettings {
    Correction mode = Correction::Shift;
    double target = .33;
    int maximumShift = 112;
};

class Samples {
public:
    void add(const QColor &surface, double weight = 1.)
    {
        if (!(weight > 0.) || !surface.isValid() || !surface.alpha()) return;
        m_weight += weight;
        m_luminance += weight * luminance(surface);
        m_samples.append({surface, weight});
    }

    QColor tone(QColor base, CorrectionSettings settings = {}, bool wasFlipped = false) const
    {
        if (!m_weight || !base.isValid() || !base.alpha()) return base;
        const double background = lightnessFromLuminance(m_luminance / m_weight);
        const auto separation = [&](QColor ink) {
            if (ink.alphaF() == 1.) return std::abs(lightness(ink) - background);
            double visible = 0.;
            for (const auto &sample : m_samples)
                visible += sample.weight * luminance(composite(sample.color, ink));
            return std::abs(lightnessFromLuminance(visible / m_weight) - background);
        };

        double best = separation(base);
        // Once flipped, require three more L* units before returning to base.
        const double threshold = settings.target + (settings.mode == Correction::Flip && wasFlipped ? .03 : 0.);
        if (best >= threshold) return base;
        const Family family = familyOf(base);
        if (settings.mode == Correction::Flip) {
            QColor opposite = family == Family::Dark ? Qt::white : Qt::black;
            opposite.setAlphaF(base.alphaF());
            return separation(opposite) > best ? opposite : base;
        }
        QColor result = base;
        for (int step = 1; step <= settings.maximumShift; ++step) {
            for (int direction : {-1, 1}) {
                const double delta = direction * step / 255.;
                const auto shift = [delta](double channel) { return std::clamp(channel + delta, 0., 1.); };
                const QColor candidate = QColor::fromRgbF(shift(base.redF()), shift(base.greenF()),
                                                          shift(base.blueF()), base.alphaF());
                if (familyOf(candidate) != family) continue;
                const double distance = separation(candidate);
                if (distance >= settings.target) return candidate;
                if (distance > best) {
                    result = candidate;
                    best = distance;
                }
            }
        }
        return result;
    }

private:
    struct Sample { QColor color; double weight; };
    QList<Sample> m_samples;
    double m_weight = 0.;
    double m_luminance = 0.;
};

// Each shaped run remembers its own foreground family as the surface moves.
class FlipHistory : public QObject {
public:
    QColor tone(const Samples &samples, QColor base, CorrectionSettings settings,
                const QObject *owner, int run = -1)
    {
        if (!owner || settings.mode != Correction::Flip) {
            if (owner) m_runs.remove(owner);
            return samples.tone(base, settings);
        }
        if (!m_connections.contains(owner)) {
            m_connections.insert(owner, connect(owner, &QObject::destroyed, this, [this, owner] {
                m_runs.remove(owner);
                m_connections.remove(owner);
            }));
        }
        auto &previous = m_runs[owner][run];
        const auto result = samples.tone(base, settings, previous.flipped && previous.base == base
                                         && previous.target == settings.target);
        previous = {base, settings.target, result != base};
        return result;
    }
private:
    struct Decision { QColor base; double target = 0.; bool flipped = false; };
    QHash<const QObject *, QHash<int, Decision>> m_runs;
    QHash<const QObject *, QMetaObject::Connection> m_connections;
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

// Divide the bounds into equal-area strata. Short rows receive a
// proportionately smaller share of the height so each point has equal weight.
template <typename Visit>
void zonePoints(QRectF bounds, int count, Visit visit)
{
    if (bounds.isEmpty()) return;
    count = std::clamp(count, 1, 256);
    const int rows = std::clamp(qRound(std::sqrt(count * bounds.height() / bounds.width())), 1, count);
    int offset = 0;
    for (int row = 0; row < rows; ++row) {
        const int columns = count / rows + (row < count % rows);
        const double y = (offset + columns * .5) / count;
        for (int col = 0; col < columns; ++col)
            visit(QPointF(bounds.x() + (col + .5) * bounds.width() / columns, bounds.y() + y * bounds.height()));
        offset += columns;
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
