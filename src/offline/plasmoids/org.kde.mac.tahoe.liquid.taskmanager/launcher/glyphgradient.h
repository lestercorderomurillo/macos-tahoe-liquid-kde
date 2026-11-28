// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QElapsedTimer>
#include <QLinearGradient>
#include <QList>
#include <algorithm>
#include <cmath>

namespace GlassInk {
class GradientTrack
{
public:
    void setTarget(const QList<QColor> &next)
    {
        if (next == m_target) return;
        m_start = next.size() == m_target.size() ? colors() : next;
        m_target = next;
        m_elapsed.restart();
    }

    bool animating() const { return m_start != m_target && m_elapsed.isValid() && m_elapsed.elapsed() < 150; }

    QList<QColor> colors() const
    {
        if (!animating()) return m_target;
        const double t = m_elapsed.elapsed() / 150.;
        const double eased = t * t * (3. - 2. * t);
        QList<QColor> result;
        for (qsizetype i = 0; i < m_target.size(); ++i) {
            const auto &a = m_start[i], &b = m_target[i];
            result.append(QColor::fromRgbF(std::lerp(a.redF(), b.redF(), eased),
                std::lerp(a.greenF(), b.greenF(), eased), std::lerp(a.blueF(), b.blueF(), eased),
                std::lerp(a.alphaF(), b.alphaF(), eased)));
        }
        return result;
    }

    QLinearGradient brush(qreal width, const QList<qreal> &centers) const
    {
        QLinearGradient gradient(0, 0, std::max(1., width), 0);
        const auto values = colors();
        for (qsizetype i = 0; i < std::min(centers.size(), values.size()); ++i)
            gradient.setColorAt(std::clamp(centers[i] / std::max(1., width), 0., 1.), values[i]);
        return gradient;
    }

private:
    QList<QColor> m_start, m_target;
    QElapsedTimer m_elapsed;
};
}
