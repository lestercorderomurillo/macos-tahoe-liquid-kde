// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QDBusConnection>
#include <QObject>
#include <QTimer>
#include <qqmlregistration.h>

class IconThemeWatcher : public QObject
{
    Q_OBJECT
    QML_ELEMENT
public:
    explicit IconThemeWatcher(QObject *parent = nullptr) : QObject(parent)
    {
        QDBusConnection::sessionBus().connect(QString(), QStringLiteral("/KIconLoader"),
            QStringLiteral("org.kde.KIconLoader"), QStringLiteral("iconChanged"), this, SLOT(refresh(int)));
    }
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void refresh(int)
    {
        // Let the platform icon loader finish invalidating the outgoing theme.
        QTimer::singleShot(0, this, &IconThemeWatcher::changed);
    }
};
