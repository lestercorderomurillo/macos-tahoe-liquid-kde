// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QColor>
#include <QElapsedTimer>
#include <QHash>
#include <QPointer>
#include <QTimer>
#include <QWindow>
#include <algorithm>
#include <functional>
#include <utility>

namespace GlassInk {
// Share one timer across all changing labels on a surface. Repeated samples
// with the same endpoint leave its timeline alone.
class Transition : public QObject
{
public:
    explicit Transition(std::function<void()> repaint) : m_repaint(std::move(repaint))
    {
        m_clock.start();
        m_timer.setInterval(16);
        m_timer.setTimerType(Qt::PreciseTimer);
        connect(&m_timer, &QTimer::timeout, this, [this] {
            const auto now = m_clock.elapsed();
            bool active = false;
            for (auto &track : m_tracks) {
                if (now >= track.start + Duration) track.from = track.to;
                active |= track.from != track.to;
            }
            if (!active) m_timer.stop();
            m_repaint();
        });
    }

    void observe(QWindow *window)
    {
        if (window == m_window) return;
        if (m_window) disconnect(m_window, nullptr, this, nullptr);
        reset();
        m_window = window;
        if (!window) return;
        connect(window, &QWindow::xChanged, this, [this] { moved(); });
        connect(window, &QWindow::yChanged, this, [this] { moved(); });
        connect(window, &QWindow::visibleChanged, this, [this](bool visible) { if (!visible) reset(); });
    }

    void reset()
    {
        m_timer.stop();
        for (const auto &track : std::as_const(m_tracks)) disconnect(track.destroyed);
        m_tracks.clear();
        m_settledAt = 0;
    }

    void moved()
    {
        const auto now = m_clock.elapsed();
        m_settledAt = now + QuietPeriod;
        for (auto &track : m_tracks) {
            track.from = track.value(now);
            track.start = m_settledAt;
        }
    }

    QColor target(const QObject *item, QColor initial) const
    {
        const auto it = m_tracks.constFind(item);
        return it == m_tracks.cend() ? initial : it->to;
    }

    QColor color(const QObject *item, QColor initial, QColor target)
    {
        if (!item) return initial;
        const auto now = m_clock.elapsed();
        auto it = m_tracks.find(item);
        if (it == m_tracks.end()) {
            Track track;
            track.from = track.to = initial;
            track.destroyed = connect(item, &QObject::destroyed, this, [this, item] { m_tracks.remove(item); });
            it = m_tracks.insert(item, track);
        }
        if (it->to != target) {
            it->from = it->value(now);
            it->to = target;
            // A moving background behind a stationary popup can also reverse
            // the target several times between compositor samples.
            const bool chattering = now - it->lastTargetChange < QuietPeriod;
            it->start = std::max(m_settledAt, chattering ? now + QuietPeriod : now);
            it->lastTargetChange = now;
            if (!m_timer.isActive()) m_timer.start();
        }
        return it->value(now);
    }

private:
    static constexpr int Duration = 250;
    static constexpr int QuietPeriod = 50;
    struct Track {
        QColor from, to;
        qint64 start = 0, lastTargetChange = -QuietPeriod;
        QMetaObject::Connection destroyed;
        QColor value(qint64 now) const
        {
            if (from == to || now >= start + Duration) return to;
            if (now <= start) return from;
            const double t = double(now - start) / Duration;
            const double eased = t * t * (3 - 2 * t);
            const auto mix = [eased](double a, double b) { return a + eased * (b - a); };
            return QColor::fromRgbF(mix(from.redF(), to.redF()), mix(from.greenF(), to.greenF()),
                                    mix(from.blueF(), to.blueF()), mix(from.alphaF(), to.alphaF()));
        }
    };
    QElapsedTimer m_clock;
    QTimer m_timer;
    QPointer<QWindow> m_window;
    QHash<const QObject *, Track> m_tracks;
    qint64 m_settledAt = 0;
    std::function<void()> m_repaint;
};
}
