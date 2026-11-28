// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QColor>
#include <QElapsedTimer>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QRect>
#include <QTimer>

// Requests contain only glyph positions. KWin addresses replies to the shell.
class InkPixels
{
public:
    using Key = QPair<double, double>;
    InkPixels()
    {
        m_age.start();
        m_flush.setSingleShot(true);
        QObject::connect(&m_flush, &QTimer::timeout, &m_flush, [this] {
            auto signal = QDBusMessage::createTargetedSignal(QStringLiteral("org.kde.KWin"),
                QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
                QStringLiteral("requestInkPixels"));
            signal << int(QCoreApplication::applicationPid()) << m_frame << m_role
                   << QJsonDocument(m_pending).toJson(QJsonDocument::Compact);
            QDBusConnection::sessionBus().send(signal);
            m_pending = {};
        });
    }
    void locate(const QRect &frame, const QString &role)
    {
        if (frame == m_frame && role == m_role) return;
        m_frame = frame;
        m_role = role;
        m_pending = {};
        m_colors.clear();
        m_flush.stop();
    }
    QColor at(QPointF p)
    {
        if (m_frame.isEmpty() || !QRectF(QPointF(), m_frame.size()).contains(p)) return {};
        const Key key{p.x(), p.y()};
        const auto now = m_age.elapsed();
        auto it = m_colors.find(key);
        if (it == m_colors.end()) {
            if (m_colors.size() >= 2048) m_colors.clear();
            it = m_colors.insert(key, Entry{});
        }
        // Renew on demand after compositor restarts or a discarded subscription.
        if (it->requested < 0 || now - it->requested > 3000) {
            it->requested = now;
            m_pending.append(QJsonArray{p.x(), p.y()});
            if (!m_flush.isActive()) m_flush.start(0);
        }
        return it->color;
    }
    bool receive(int pid, const QRect &frame, const QString &role, const QByteArray &data)
    {
        if (pid != QCoreApplication::applicationPid() || frame != m_frame || role != m_role) return false;
        bool changed = false;
        const auto entries = QJsonDocument::fromJson(data).array();
        for (const auto &entry : entries) {
            const auto values = entry.toArray();
            if (values.size() != 3) continue;
            auto it = m_colors.find({values[0].toDouble(), values[1].toDouble()});
            if (it == m_colors.end()) continue;
            const QColor color = QColor::fromRgb(QRgb(values[2].toInt()));
            if (it->color != color) { it->color = color; changed = true; }
        }
        return changed;
    }
private:
    struct Entry { QColor color; qint64 requested = -1; };
    QElapsedTimer m_age;
    QMap<Key, Entry> m_colors;
    QTimer m_flush;
    QJsonArray m_pending;
    QRect m_frame;
    QString m_role;
};
