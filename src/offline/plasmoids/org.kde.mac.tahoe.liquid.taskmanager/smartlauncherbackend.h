/*
    SPDX-FileCopyrightText: 2016, 2019 Kai Uwe Broulik <kde@privat.broulik.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include <QDBusContext>
#include <QHash>
#include <QObject>
#include <QVariantMap>

#include <jobsmodel.h>

class QDBusServiceWatcher;
class QString;

namespace NotificationManager
{
class Settings;
}

namespace SmartLauncher
{
struct Entry {
    int count = 0;
    bool countVisible = false;
    int progress = 0;
    bool progressVisible = false;
    bool urgent = false;
};

class Backend : public QObject, protected QDBusContext
{
    Q_OBJECT

public:
    explicit Backend(QObject *parent = nullptr);
    ~Backend() override;

    bool hasLauncher(const QString &storageId) const;

    int count(const QString &uri) const;
    bool countVisible(const QString &uri) const;
    int progress(const QString &uri) const;
    bool progressVisible(const QString &uri) const;
    bool urgent(const QString &uri) const;

    QHash<QString, QString> unityMappingRules() const;

Q_SIGNALS:
    void countChanged(const QString &uri, int count);
    void countVisibleChanged(const QString &uri, bool countVisible);
    void progressChanged(const QString &uri, int progress);
    void progressVisibleChanged(const QString &uri, bool progressVisible);
    void urgentChanged(const QString &uri, bool urgent);

    void reloadRequested(const QString &uri);
    void launcherRemoved(const QString &uri);

private Q_SLOTS:
    void update(const QString &uri, const QMap<QString, QVariant> &properties);

private:
    void reload();
    void setupUnity();
    void setupApplicationJobs();

    void onServiceUnregistered(const QString &service);

    template<typename T>
    void updateLauncherProperty(const QString &storageId,
                                const QVariantMap &properties,
                                const QString &property,
                                T *entryMember,
                                T (Backend::*getter)(const QString &) const,
                                void (Backend::*changeSignal)(const QString &, T))
    {
        auto foundProperty = properties.constFind(property);
        if (foundProperty != properties.constEnd()) {
            const T oldSanitizedValue = ((this)->*getter)(storageId);

            T newValue = foundProperty->value<T>();
            *entryMember = newValue;

            const T newSanitizedValue = ((this)->*getter)(storageId);

            if (newSanitizedValue != oldSanitizedValue) {
                Q_EMIT((this)->*changeSignal)(storageId, newSanitizedValue);
            }
        }
    }

    bool doNotDisturbMode() const;

    QDBusServiceWatcher *m_watcher;
    QHash<QString, QString> m_dbusServiceToLauncherUrl;
    QHash<QString, QString> m_launcherUrlToStorageId;
    QHash<QString, QString> m_unityMappingRules;

    NotificationManager::JobsModel::Ptr m_jobsModel;

    NotificationManager::Settings *m_settings = nullptr;

    QHash<QString, Entry> m_launchers;

    QStringList m_badgeBlacklist;

    bool m_available = false;
};

} // namespace SmartLauncher
