// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <Plasma/Theme>
#include <QDBusConnection>
#include <QObject>
#include <QTimer>
#include <qqmlregistration.h>

class IconThemeWatcher : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString plasmaThemeName READ plasmaThemeName NOTIFY changed)
public:
    explicit IconThemeWatcher(QObject *parent = nullptr) : QObject(parent)
    {
        connect(&m_theme, &Plasma::Theme::themeChanged, this, &IconThemeWatcher::changed);
        QDBusConnection::sessionBus().connect(QString(), QStringLiteral("/KIconLoader"),
            QStringLiteral("org.kde.KIconLoader"), QStringLiteral("iconChanged"), this, SLOT(refresh(int)));
    }
    QString plasmaThemeName() const { return m_theme.themeName(); }
Q_SIGNALS:
    void changed();
private:
    Plasma::Theme m_theme;
private Q_SLOTS:
    void refresh(int)
    {
        // Let the platform icon loader finish invalidating the outgoing theme.
        QTimer::singleShot(0, this, &IconThemeWatcher::changed);
    }
};
