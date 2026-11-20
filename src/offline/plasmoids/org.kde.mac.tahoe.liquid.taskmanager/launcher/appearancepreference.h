// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <KDirWatch>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <qqmlregistration.h>

class AppearancePreference : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString mode READ mode NOTIFY changed)
public:
    explicit AppearancePreference(QObject *parent = nullptr) : QObject(parent)
    {
        connect(&m_watch, &KDirWatch::dirty, this, &AppearancePreference::reload);
        connect(&m_watch, &KDirWatch::created, this, &AppearancePreference::reload);
        connect(&m_watch, &KDirWatch::deleted, this, &AppearancePreference::reload);
        m_watch.addFile(m_path);
        reload();
    }

    QString mode() const { return m_mode; }

Q_SIGNALS:
    void changed();

private:
    void reload()
    {
        QFile file(m_path);
        QString selected;
        if (file.open(QIODevice::ReadOnly)) {
            selected = QJsonDocument::fromJson(file.readAll()).object().value(QStringLiteral("preference")).toString();
        }
        if (selected == QStringLiteral("native-auto")) selected = QStringLiteral("auto");
        if (selected == m_mode) return;
        m_mode = selected;
        Q_EMIT changed();
    }

    const QString m_path = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation)
        + QStringLiteral("/mac-tahoe-liquid-kde/appearance.json");
    KDirWatch m_watch;
    QString m_mode;
};
