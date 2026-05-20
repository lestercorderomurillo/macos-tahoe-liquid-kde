/*
    SPDX-FileCopyrightText: 2016 Chinmoy Ranjan Pradhan <chinmoyrp65@gmail.com>
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#pragma once

#include <KWindowSystem>
#include <Plasma/Containment>
#include <QAbstractListModel>
#include <QAction>
#include <QPointer>
#include <QRect>
#include <QStringList>
#include <qqmlregistration.h>
#include <tasksmodel.h>

class QMenu;
class QModelIndex;
class QDBusServiceWatcher;
class KDBusMenuImporter;

/**
 * Flattened MenuModel exposing the active window's application menu.
 *
 * Each row is one top-level menu entry (File / Edit / View / …). The
 * actual submenu tree is reachable via the ``ActionRole`` data, which
 * QML uses to populate native QMenu popups on click.
 *
 * Data source is the AppMenu DBus protocol (GTK and Qt both implement
 * it). KDBusMenuImporter watches the registrar for the active window's
 * service name + object path; we listen for ``modelNeedsUpdate`` and
 * republish accordingly.
 *
 * Visibility logic: the menu is hidden when its containment is in
 * PassiveStatus AND the active window is on a different screen. When
 * ``allScreens`` is true we always show the active window's menu
 * regardless of which screen it lives on.
 */
class AppMenuModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT

    /// Human-readable name of the focused application — what the menu
    /// shows when the user clicks the app-name button.
    Q_PROPERTY(QString activeAppName READ activeAppName NOTIFY activeAppNameChanged)

    /// True iff the active window publishes an AppMenu we can render.
    Q_PROPERTY(bool menuAvailable READ menuAvailable WRITE setMenuAvailable NOTIFY menuAvailableChanged)

    /// True when the menubar is actually painted (combination of
    /// containment status + active-window-on-our-screen).
    Q_PROPERTY(bool visible READ visible NOTIFY visibleChanged)

    /// When false, only show menus for windows on this output. When
    /// true, mirror the global active window's menu regardless of screen.
    Q_PROPERTY(bool allScreens READ allScreens WRITE setallScreens NOTIFY allScreensChanged)

    /// Plasma containment status — gates visibility (Passive = panel
    /// hidden / minimized → don't render the menubar).
    Q_PROPERTY(Plasma::Types::ItemStatus containmentStatus MEMBER m_containmentStatus NOTIFY containmentStatusChanged)

    /// Geometry of our screen — used to decide whether a window lives
    /// on the same output as the menubar applet.
    Q_PROPERTY(QRect screenGeometry READ screenGeometry WRITE setScreenGeometry NOTIFY screenGeometryChanged)

public:
    // Construction

    explicit AppMenuModel(QObject* parent = nullptr);
    ~AppMenuModel() override;

    // Model roles

    enum AppMenuRole
    {
        MenuRole = Qt::UserRole + 1, ///< Menu text (string) for QML to render.
        ActionRole, ///< Underlying QAction* (carries the submenu).
    };

    // QAbstractListModel overrides

    QVariant data(const QModelIndex& index, int role) const override;
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    QHash<int, QByteArray> roleNames() const override;

    // External API

    /// Swap the watched dbus service / object — called when the active
    /// window changes. Hooks the new importer up and tears down the old.
    void updateApplicationMenu(const QString& serviceName, const QString& menuObjectPath);

    QString activeAppName() const;
    bool menuAvailable() const;
    void setMenuAvailable(bool set);
    bool allScreens() const;
    void setallScreens(bool allScreens);
    bool visible() const;
    QRect screenGeometry() const;
    void setScreenGeometry(QRect geometry);

    /// Flatten the full menu tree into a single QAction list — used by
    /// the QML search field to find entries by name without walking
    /// nested submenus.
    QList<QAction*> flatActionList();

    /// Underlying TasksModel — exposed for QML to query the active
    /// window's icon / title without a second model.
    TaskManager::TasksModel* tasksModel() const;

Q_SIGNALS:
    /// QML connects these to its menubar buttons and search field.
    void requestActivateIndex(int index);
    void bringToFocus(int index);

    void activeAppNameChanged();
    void allScreensChanged();
    void menuAvailableChanged();
    void modelNeedsUpdate();
    void containmentStatusChanged();
    void screenGeometryChanged();
    void visibleChanged();

private Q_SLOTS:
    /// Re-attach to the new active window's AppMenu service.
    void onActiveWindowChanged();

    void setVisible(bool visible);

    /// Coalesced ``modelNeedsUpdate`` handler — refreshes the row count
    /// + cached top-level action list.
    void update();

private:
    // Visibility / model state

    bool m_menuAvailable = false;
    bool m_allScreens = true;
    bool m_updatePending = false;
    bool m_visible = true;
    Plasma::Types::ItemStatus m_containmentStatus = Plasma::Types::PassiveStatus;

    // Task tracking + menu source

    TaskManager::TasksModel* m_tasksModel;
    std::unique_ptr<QMenu> m_searchMenu;
    QPointer<QMenu> m_menu;
    QPointer<QAction> m_searchAction;
    QList<QAction*> m_currentSearchActions;

    /// Remove the synthetic search results from the menu before rebuilding.
    void removeSearchActionsFromMenu();

    /// Splice search results matching ``filter`` into the menu under a
    /// "Search" group.
    void insertSearchActionsIntoMenu(const QString& filter = QString());

    // DBus bookkeeping

    QDBusServiceWatcher* m_serviceWatcher;
    QString m_serviceName;
    QString m_menuObjectPath;
    std::unique_ptr<KDBusMenuImporter> m_importer;
};
