/*
    SPDX-FileCopyrightText: 2016, 2019 Kai Uwe Broulik <kde@privat.broulik.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "smartlauncherbackend.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusServiceWatcher>
#include <QDebug>

#include <KConfigGroup>
#include <KService>
#include <KSharedConfig>

#include <algorithm>
#include <cmath>
#include <limits>

#include "log_settings.h"
#include <settings.h>

using namespace SmartLauncher;
using namespace NotificationManager;

// Lifecycle

Backend::Backend(QObject* parent)
    : QObject(parent)
    , m_watcher(new QDBusServiceWatcher(this))
    , m_jobsModel(nullptr)
    , m_settings(new Settings(this))
{
    m_watcher->setConnection(QDBusConnection::sessionBus());
    m_watcher->setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
    connect(m_watcher, &QDBusServiceWatcher::serviceUnregistered, this, &Backend::onServiceUnregistered);

    setupUnity();

    reload();
    connect(m_settings, &Settings::settingsChanged, this, &Backend::reload);
}

Backend::~Backend() = default;

// Internal setup

void Backend::reload()
{
    m_badgeBlacklist = m_settings->badgeBlacklistedApplications();

    std::transform(m_badgeBlacklist.begin(), m_badgeBlacklist.end(), m_badgeBlacklist.begin(),
        [](const QString& desktopEntry) -> QString { return desktopEntry + QStringLiteral(".desktop"); });

    if (!m_jobsModel) {
        m_jobsModel = JobsModel::createJobsModel();
        m_jobsModel->init();
    }

    Q_EMIT reloadRequested(QString());
}

bool Backend::doNotDisturbMode() const
{
    return m_settings->notificationsInhibitedByApplication()
        || (m_settings->notificationsInhibitedUntil().isValid() && m_settings->notificationsInhibitedUntil() > QDateTime::currentDateTimeUtc());
}

void Backend::setupUnity()
{
    auto sessionBus = QDBusConnection::sessionBus();

    if (!sessionBus.connect(
            {}, {}, QStringLiteral("com.canonical.Unity.LauncherEntry"), QStringLiteral("Update"), this, SLOT(update(QString, QMap<QString, QVariant>)))) {
        qCWarning(TASKMANAGER_DEBUG) << "failed to register Update signal";
        return;
    }

    if (!sessionBus.registerObject(QStringLiteral("/Unity"), this)) {
        qCWarning(TASKMANAGER_DEBUG) << "Failed to register unity object";
        return;
    }

    if (!sessionBus.registerService(QStringLiteral("com.canonical.Unity"))) {
        qCWarning(TASKMANAGER_DEBUG) << "Failed to register unity service";
    }

    KConfigGroup grp(KSharedConfig::openConfig(QStringLiteral("taskmanagerrulesrc")), QStringLiteral("Unity Launcher Mapping"));

    const QStringList keys = grp.keyList();
    for (const QString& key : keys) {
        const QString& value = grp.readEntry(key, QString());
        if (value.isEmpty()) {
            continue;
        }

        m_unityMappingRules.insert(key, value);
    }
}

// Per-launcher queries (DND-aware)

bool Backend::hasLauncher(const QString& storageId) const
{
    return m_launchers.contains(storageId);
}

int Backend::count(const QString& uri) const
{
    if (!m_settings->badgesInTaskManager() || doNotDisturbMode() || m_badgeBlacklist.contains(uri)) {
        return 0;
    }
    return m_launchers.value(uri).count;
}

bool Backend::countVisible(const QString& uri) const
{
    if (!m_settings->badgesInTaskManager() || doNotDisturbMode() || m_badgeBlacklist.contains(uri)) {
        return false;
    }
    return m_launchers.value(uri).countVisible;
}

int Backend::progress(const QString& uri) const
{
    return m_launchers.value(uri).progress;
}

bool Backend::progressVisible(const QString& uri) const
{
    return m_launchers.value(uri).progressVisible;
}

bool Backend::urgent(const QString& uri) const
{
    return m_launchers.value(uri).urgent;
}

QHash<QString, QString> Backend::unityMappingRules() const
{
    return m_unityMappingRules;
}

// DBus event handlers

/// Slot bound to Unity ``Update(string uri, dict<string,variant>)``.
/// Walks the property dict and forwards each known key to
/// updateLauncherProperty, which handles the "did the sanitised value
/// change → emit changed signal" diff.
void Backend::update(const QString& uri, const QMap<QString, QVariant>& properties)
{
    Q_ASSERT(calledFromDBus());

    QString storageId;

    auto foundStorageId = m_launcherUrlToStorageId.constFind(uri);
    if (foundStorageId == m_launcherUrlToStorageId.constEnd()) {
        const QString applicationSchemePrefix = QStringLiteral("application://");

        QString normalizedUri = uri;
        if (normalizedUri.startsWith(applicationSchemePrefix)) {
            normalizedUri = uri.mid(applicationSchemePrefix.length());
        }

        KService::Ptr service = KService::serviceByStorageId(normalizedUri);
        if (!service) {
            qCWarning(TASKMANAGER_DEBUG) << "Failed to find service for Unity Launcher" << uri;
            return;
        }

        storageId = service->storageId();
        m_launcherUrlToStorageId.insert(uri, storageId);

        m_dbusServiceToLauncherUrl.insert(message().service(), uri);
        m_watcher->addWatchedService(message().service());
    } else {
        storageId = *foundStorageId;
    }

    auto foundEntry = m_launchers.find(storageId);
    if (foundEntry == m_launchers.end()) {
        Entry entry;
        foundEntry = m_launchers.insert(storageId, entry);
    }

    auto propertiesEnd = properties.constEnd();

    auto foundCount = properties.constFind(QStringLiteral("count"));
    if (foundCount != propertiesEnd) {
        qint64 newCount = foundCount->toLongLong();
        if (newCount >= std::numeric_limits<int>::min()
            && newCount <= std::numeric_limits<int>::max()) {
            int saneCount = static_cast<int>(newCount);
            if (saneCount != foundEntry->count) {
                foundEntry->count = saneCount;
                Q_EMIT countChanged(storageId, saneCount);
            }
        }
    }

    updateLauncherProperty(
        storageId, properties, QStringLiteral("count-visible"), &foundEntry->countVisible, &Backend::countVisible, &Backend::countVisibleChanged);

    auto foundProgress = properties.constFind(QStringLiteral("progress"));
    if (foundProgress != propertiesEnd) {
        const int oldSanitizedProgress = progress(storageId);

        double progressValue = foundProgress->toDouble();
        if (!std::isfinite(progressValue)) {
            progressValue = 0.0;
        }
        foundEntry->progress = qRound(progressValue * 100);

        const int newSanitizedProgress = progress(storageId);

        if (oldSanitizedProgress != newSanitizedProgress) {
            Q_EMIT progressChanged(storageId, newSanitizedProgress);
        }
    }

    updateLauncherProperty(
        storageId, properties, QStringLiteral("progress-visible"), &foundEntry->progressVisible, &Backend::progressVisible, &Backend::progressVisibleChanged);
    updateLauncherProperty(storageId, properties, QStringLiteral("urgent"), &foundEntry->urgent, &Backend::urgent, &Backend::urgentChanged);
}

void Backend::onServiceUnregistered(const QString& service)
{
    const QString& launcherUrl = m_dbusServiceToLauncherUrl.take(service);
    if (launcherUrl.isEmpty()) {
        return;
    }

    const QString& storageId = m_launcherUrlToStorageId.take(launcherUrl);
    if (storageId.isEmpty()) {
        return;
    }

    m_launchers.remove(storageId);
    Q_EMIT launcherRemoved(storageId);
}

#include "moc_smartlauncherbackend.cpp"
