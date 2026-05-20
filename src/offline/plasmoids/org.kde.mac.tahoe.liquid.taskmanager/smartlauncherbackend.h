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

namespace NotificationManager {
class Settings;
}

namespace SmartLauncher {

/**
 * Per-launcher state cached by Backend.
 *
 * Mirrors the Unity LauncherEntry properties: numeric count badge,
 * a 0..100 progress bar, and an "urgent" attention flag. Each launcher
 * (one per pinned/running app) has one Entry instance, keyed by storage
 * id (the basename of the .desktop file).
 */
struct Entry
{
    int count = 0;
    bool countVisible = false;
    int progress = 0;
    bool progressVisible = false;
    bool urgent = false;
};

/**
 * Singleton dbus backend exposing the Unity LauncherEntry protocol to QML.
 *
 * Owns:
 *   - A QDBusServiceWatcher tracking which apps currently expose a
 *     ``com.canonical.Unity.LauncherEntry`` interface.
 *   - The mapping from .desktop URLs to storage ids (and the inverse
 *     ``unityMappingRules`` so legacy callers can resolve the other way).
 *   - The NotificationManager JobsModel — long-running file copies /
 *     downloads show up as progress bars on the launcher icon.
 *   - The do-not-disturb-aware badge blacklist so silenced apps don't
 *     poke the user with unread badges.
 *
 * Shared across all SmartLauncher::Item instances via the static
 * ``s_backend`` weak_ptr in smartlauncheritem.cpp.
 */
class Backend : public QObject, protected QDBusContext
{
    Q_OBJECT

public:
    // Lifecycle

    explicit Backend(QObject* parent = nullptr);
    ~Backend() override;

    // Queries

    /// True iff we've ever seen a LauncherEntry for ``storageId``.
    bool hasLauncher(const QString& storageId) const;

    int count(const QString& uri) const;
    bool countVisible(const QString& uri) const;
    int progress(const QString& uri) const;
    bool progressVisible(const QString& uri) const;

    /// Urgent (= attention) flag with DND awareness — silenced apps
    /// never report urgent regardless of what they send.
    bool urgent(const QString& uri) const;

    /// Snapshot of the live launcher-URL → storage-id mapping.
    /// Read-only — mutations happen internally via dbus events.
    QHash<QString, QString> unityMappingRules() const;

Q_SIGNALS:
    // Per-launcher change signals (Item subscribes via direct connect)

    void countChanged(const QString& uri, int count);
    void countVisibleChanged(const QString& uri, bool countVisible);
    void progressChanged(const QString& uri, int progress);
    void progressVisibleChanged(const QString& uri, bool progressVisible);
    void urgentChanged(const QString& uri, bool urgent);

    /// "Reload everything you know about this launcher" — fired when
    /// the underlying app reappears after going away.
    void reloadRequested(const QString& uri);

    /// LauncherEntry vanished — Items should clear their state.
    void launcherRemoved(const QString& uri);

private Q_SLOTS:
    /// Dbus slot bound to Unity ``Update(string uri, dict<string,variant>)``.
    /// Delegates to ``updateLauncherProperty`` for each known key.
    void update(const QString& uri, const QMap<QString, QVariant>& properties);

private:
    /// Re-scan the desktop file system for all known launchers and
    /// rebuild the URL ↔ storage-id mappings.
    void reload();

    /// Register Backend as the ``com.canonical.Unity`` service on the
    /// session bus. Listens for LauncherEntry properties.
    void setupUnity();

    /// Subscribe to the NotificationManager JobsModel so long-running
    /// jobs become progress bars on the matching launcher icon.
    void setupApplicationJobs();

    /// Cleanup hook when a Unity-publishing app exits.
    void onServiceUnregistered(const QString& service);

    /// Generic "did the value change, and if so emit?" helper used by
    /// update(). Templated on the value type so callers don't have to
    /// repeat the read/compare/emit triple per property.
    template <typename T>
    void updateLauncherProperty(const QString& storageId, const QVariantMap& properties, const QString& property, T* entryMember,
        T (Backend::*getter)(const QString&) const, void (Backend::*changeSignal)(const QString&, T))
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

    /// True iff the NotificationManager's global DND switch is on.
    /// Counts but not progress are suppressed when this is true (the
    /// user wants quiet, but a copy job should still show progress).
    bool doNotDisturbMode() const;

    // Members

    QDBusServiceWatcher* m_watcher;
    QHash<QString, QString> m_dbusServiceToLauncherUrl;
    QHash<QString, QString> m_launcherUrlToStorageId;
    QHash<QString, QString> m_unityMappingRules;

    NotificationManager::JobsModel::Ptr m_jobsModel;
    NotificationManager::Settings* m_settings = nullptr;

    QHash<QString, Entry> m_launchers;
    QStringList m_badgeBlacklist;

    bool m_available = false;
};

} // namespace SmartLauncher
