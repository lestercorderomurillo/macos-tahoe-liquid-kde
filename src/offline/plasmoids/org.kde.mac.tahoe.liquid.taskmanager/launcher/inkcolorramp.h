// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "glyphgradient.h"
#include <QPainter>
#include <QQuickPaintedItem>
#include <QTimer>
#include <QtQml/qqmlregistration.h>

class InkColorRamp : public QQuickPaintedItem
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QVariantList rows READ rows WRITE setRows NOTIFY rowsChanged)
public:
    explicit InkColorRamp(QQuickItem *parent = nullptr) : QQuickPaintedItem(parent)
    {
        m_timer.setInterval(16);
        m_timer.setTimerType(Qt::PreciseTimer);
        connect(&m_timer, &QTimer::timeout, this, [this] {
            if (!std::any_of(m_lines.cbegin(), m_lines.cend(), [](const Line &line) { return line.track.animating(); }))
                m_timer.stop();
            update();
        });
    }
    QVariantList rows() const { return m_rows; }
    void setRows(const QVariantList &rows)
    {
        if (m_rows == rows) return;
        m_rows = rows;
        m_lines.resize(rows.size());
        for (qsizetype i = 0; i < rows.size(); ++i) {
            const auto row = rows[i].toMap();
            auto &line = m_lines[i];
            line.top = row.value(QStringLiteral("top")).toReal();
            line.centers.clear();
            QList<QColor> colors;
            const auto stops = row.value(QStringLiteral("stops")).toList();
            for (const auto &stop : stops) {
                const auto data = stop.toMap();
                line.centers.append(data.value(QStringLiteral("x")).toReal());
                colors.append(QColor::fromString(data.value(QStringLiteral("color")).toString()));
            }
            line.track.setTarget(colors);
            if (line.track.animating() && !m_timer.isActive()) m_timer.start();
        }
        update();
        Q_EMIT rowsChanged();
    }
    void paint(QPainter *painter) override
    {
        for (qsizetype i = 0; i < m_lines.size(); ++i) {
            const auto &line = m_lines[i];
            const qreal top = i ? std::round(line.top) : 0.;
            const qreal end = i + 1 < m_lines.size() ? std::round(m_lines[i+1].top) : height();
            painter->fillRect(QRectF(0, top, width(), end - top), line.track.brush(width(), line.centers));
        }
    }
Q_SIGNALS:
    void rowsChanged();
private:
    struct Line { qreal top = 0; QList<qreal> centers; GlassInk::GradientTrack track; };
    QVariantList m_rows;
    QList<Line> m_lines;
    QTimer m_timer;
};
