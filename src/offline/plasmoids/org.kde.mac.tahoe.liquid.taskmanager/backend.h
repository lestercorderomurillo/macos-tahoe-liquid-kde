/*
    SPDX-FileCopyrightText: 2013-2016 Eike Hein <hein@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include <KConfigWatcher>

#include <QObject>
#include <QRect>

#include <netwm.h>
#include <qqmlregistration.h>
#include <qwindowdefs.h>

#include "kactivitymanagerd_plugins_settings.h"

class QAction;
class QActionGroup;
class QQuickItem;
class QQuickWindow;
class QJsonArray;

namespace KActivities {
class Consumer;
}

/**
 * Task-manager QML helper backend.
 *
 * Exposes the bits of QtX11Extras / Solid / KActivities / KIO that the
 * QML side can't reach from a sandboxed plasmoid context. Lives one
 * instance per IconTasks/SmartLauncher root item — see
 * ``contents/ui/main.qml`` for the QML side.
 *
 * Most slots are ``Q_INVOKABLE`` rather than ``Q_PROPERTY``-bound so
 * QML can call them on demand without holding open file handles or
 * polling resource lists.
 */
class Backend : public QObject
{
    Q_OBJECT
    QML_ELEMENT

public:
    // Public types

    /// Middle-mouse action selector — mirrors the kcm "Middle click on
    /// task" combo. ``ToggleGrouping`` flips just the per-task grouping
    /// flag (group same-window vs separate icons).
    enum MiddleClickAction
    {
        None = 0,
        Close,
        NewInstance,
        ToggleMinimized,
        ToggleGrouping,
        BringToCurrentDesktop,
    };

    Q_ENUM(MiddleClickAction)

    // Construction

    /// Allocates the KActivities consumer + the activity-manager
    /// settings watcher. ``parent`` is normally the QML engine itself.
    explicit Backend(QObject* parent = nullptr);
    ~Backend() override;

    // QML-callable API

    /// Build the per-launcher jump list (KIO "Open in new window",
    /// recent documents, application-defined actions). The returned
    /// QActions are parented to ``parent`` so QML can destroy them as
    /// a group when the menu closes.
    Q_INVOKABLE QVariantList jumpListActions(const QUrl& launcherUrl, QObject* parent);

    /// Places sidebar entries (Home, Trash, custom locations). When
    /// ``showAllPlaces`` is false we expose only the user's pinned
    /// shortcuts.
    Q_INVOKABLE QVariantList placesActions(const QUrl& launcherUrl, bool showAllPlaces, QObject* parent);

    /// Recent-document QActions for ``launcherUrl``'s associated app.
    /// Activating one opens the file via the same app the task icon
    /// represents.
    Q_INVOKABLE QVariantList recentDocumentActions(const QUrl& launcherUrl, QObject* parent);

    /// Add ``action`` to the shared QActionGroup so the QML side can
    /// render radio-style selectors without having to know group
    /// membership.
    Q_INVOKABLE void setActionGroup(QAction* action) const;

    /// Convert a QML item's bounding rect to global screen coords —
    /// useful for context-menu placement.
    Q_INVOKABLE QRect globalRect(QQuickItem* item) const;

    /// True iff ``url`` resolves to an application (``.desktop`` file or
    /// ``applications:`` scheme), as opposed to a file or directory.
    Q_INVOKABLE bool isApplication(const QUrl& url) const;

    /// Walk the /proc/$pid/stat tree to find ``pid``'s parent. Returns
    /// 0 when /proc isn't available (sandbox / non-Linux).
    Q_INVOKABLE qint64 parentPid(qint64 pid) const;

    /// Static helpers — also Q_INVOKABLE so QML can call without an
    /// instance.

    /// Decodes the historical ``applications://`` URL scheme used by
    /// KDE's app menu into a plain ``file:///`` path on the .desktop.
    Q_INVOKABLE static QUrl tryDecodeApplicationsUrl(const QUrl& launcherUrl);

    /// XDG categories declared by ``launcherUrl``'s .desktop file —
    /// used to filter the launcher's "Show in category" submenu.
    Q_INVOKABLE static QStringList applicationCategories(const QUrl& launcherUrl);

Q_SIGNALS:
    // Signals (QML connects via on*Changed handlers)

    /// Emitted when the user asks to pin an app to the launcher via
    /// the right-click menu.
    void addLauncher(const QUrl& url) const;

    /// "Show All Places" selected in the places submenu — QML
    /// rebuilds the menu with showAllPlaces=true.
    void showAllPlaces();

private Q_SLOTS:
    /// Lambda-friendly slot for the recent-document QActions. The
    /// sending QAction carries the document URL in its ``data()``.
    void handleRecentDocumentAction() const;

private:
    /// Build the System Settings actions section (Display, Wallpaper, …)
    /// that lives at the bottom of the desktop jump list.
    QVariantList systemSettingsActions(QObject* parent) const;

    // Members

    QActionGroup* m_actionGroup = nullptr;
    KActivities::Consumer* m_activitiesConsumer = nullptr;

    KActivityManagerdPluginsSettings m_activityManagerPluginsSettings;
    KConfigWatcher::Ptr m_activityManagerPluginsSettingsWatcher;
};
