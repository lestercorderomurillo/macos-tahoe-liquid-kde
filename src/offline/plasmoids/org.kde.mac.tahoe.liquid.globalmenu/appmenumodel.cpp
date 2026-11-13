/*
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-FileCopyrightText: 2016 Chinmoy Ranjan Pradhan <chinmoyrp65@gmail.com>
    SPDX-FileCopyrightText: 2026 QuickBar contributors
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#include "appmenumodel.h"
#include "quickbarmenuhelpers.h"
#include "menushortcutsender.h"
#include <QTimer>

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusServiceWatcher>
#include <QGuiApplication>
#include <QMenu>

#include <KLocalizedString>
#include <QLineEdit>
#include <QListView>
#include <QWidgetAction>
#include <algorithm>

#include "dbusmenuimporter.h"
#include <abstracttasksmodel.h>

class KDBusMenuImporter : public DBusMenuImporter
{
public:
    KDBusMenuImporter(const QString& service, const QString& path)
        : DBusMenuImporter(service, path)
    { }

protected:
    QIcon iconForName(const QString& name) override { return QIcon::fromTheme(name); }
};

// Lifecycle

/// Wire up the TasksModel subscriptions + DBus service watcher. On
/// Wayland we additionally build a search QMenu with a QLineEdit so
/// the user can filter through deeply-nested menu actions.
AppMenuModel::AppMenuModel(QObject* parent)
    : QAbstractListModel(parent)
    , m_tasksModel(new TaskManager::TasksModel(this))
    , m_shortcutSender(new MenuShortcutSender(this))
    , m_serviceWatcher(new QDBusServiceWatcher(this))
{
    m_tasksModel->setFilterByScreen(!m_allScreens);
    connect(m_tasksModel, &TaskManager::TasksModel::activeTaskChanged, this, &AppMenuModel::onActiveWindowChanged);
    connect(m_tasksModel, &TaskManager::TasksModel::dataChanged,
        [this](const QModelIndex& topLeft, const QModelIndex& bottomRight, const QList<int>& roles = QList<int>()) {
            Q_UNUSED(topLeft)
            Q_UNUSED(bottomRight)
            if (roles.contains(TaskManager::AbstractTasksModel::ApplicationMenuObjectPath)
                || roles.contains(TaskManager::AbstractTasksModel::ApplicationMenuServiceName) || roles.isEmpty()) {
                onActiveWindowChanged();
            }
        });
    connect(m_tasksModel, &TaskManager::TasksModel::activityChanged, this, &AppMenuModel::onActiveWindowChanged);
    connect(m_tasksModel, &TaskManager::TasksModel::virtualDesktopChanged, this, &AppMenuModel::onActiveWindowChanged);
    connect(m_tasksModel, &TaskManager::TasksModel::countChanged, this, &AppMenuModel::onActiveWindowChanged);
    connect(m_tasksModel, &TaskManager::TasksModel::screenGeometryChanged, this, &AppMenuModel::screenGeometryChanged);
    // A focus change can arrive while the panel still accepts input. Replay
    // it when the panel releases focus, even if activeTask does not change again.
    connect(this, &AppMenuModel::containmentStatusChanged, this, &AppMenuModel::onActiveWindowChanged);

    connect(this, &AppMenuModel::modelNeedsUpdate, this, [this] {
        if (!m_updatePending) {
            m_updatePending = true;
            QMetaObject::invokeMethod(this, "update", Qt::QueuedConnection);
        }
    });

    connect(m_shortcutSender, &MenuShortcutSender::availabilityChanged, this, [this] {
        if (m_genericMenu) {
            for (auto *action : m_genericMenu->findChildren<QAction *>()) {
                if (!action->shortcut().isEmpty()) action->setEnabled(m_shortcutSender->available());
            }
        }
    });
    onActiveWindowChanged();

    m_serviceWatcher->setConnection(QDBusConnection::sessionBus());
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceUnregistered, this, [this](const QString& serviceName) {
        if (serviceName == m_serviceName) {
            Q_EMIT menuSourceAboutToChange();
            removeSearchActionsFromMenu();
            m_menu.clear();
            m_importer.reset();
            setMenuAvailable(false);
            updateGenericMenu();
            Q_EMIT modelNeedsUpdate();
        }
    });
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceRegistered, this, [this](const QString& serviceName) {
        if (serviceName == m_serviceName) {
            updateApplicationMenu(m_serviceName, m_menuObjectPath);
        }
    });

    {
        m_searchAction = new QAction(this);
        m_searchAction->setText(i18n("Search"));
        m_searchAction->setObjectName(QStringLiteral("appmenu"));

        m_searchMenu.reset(new QMenu);
        auto searchAction = new QWidgetAction(this);
        auto searchBar = new QLineEdit;
        searchBar->setClearButtonEnabled(true);
        searchBar->setPlaceholderText(i18n("Search…"));
        searchBar->setMinimumWidth(200);
        searchBar->setContentsMargins(4, 4, 4, 4);
        connect(m_tasksModel, &TaskManager::TasksModel::activeTaskChanged, searchBar, [searchBar]() { searchBar->setText(QString()); });
        connect(searchBar, &QLineEdit::textChanged, this, [searchBar, this]() mutable { insertSearchActionsIntoMenu(searchBar->text()); });
        connect(searchBar, &QLineEdit::returnPressed, this, [this]() mutable {
            if (!m_currentSearchActions.empty() && m_currentSearchActions.constFirst()
                && m_currentSearchActions.constFirst()->isEnabled()
                && m_currentSearchActions.constFirst()->isVisible()) {
                m_currentSearchActions.constFirst()->trigger();
            }
        });
        connect(this, &AppMenuModel::modelNeedsUpdate, searchBar, [this, searchBar]() mutable { insertSearchActionsIntoMenu(searchBar->text()); });
        connect(m_searchMenu.get(), &QMenu::aboutToShow, searchBar, [searchBar]() {
            QTimer::singleShot(0, searchBar, [searchBar]() {
                searchBar->setFocus(Qt::PopupFocusReason);
                searchBar->selectAll();
            });
        });
        searchAction->setDefaultWidget(searchBar);
        m_searchMenu->addAction(searchAction);
        m_searchMenu->addSeparator();
        m_searchAction->setMenu(m_searchMenu.get());
    }
}

AppMenuModel::~AppMenuModel()
{
    Q_EMIT menuSourceAboutToChange();
    removeSearchActionsFromMenu();
}

// Property accessors

QString AppMenuModel::activeAppName() const
{
    const QModelIndex idx = m_tasksModel->activeTask();
    if (!idx.isValid())
        return {};
    return m_tasksModel->data(idx, TaskManager::AbstractTasksModel::AppName).toString();
}

bool AppMenuModel::enableMenuSearch() const
{
    return m_enableMenuSearch;
}

void AppMenuModel::setEnableMenuSearch(bool enabled)
{
    if (m_enableMenuSearch == enabled) {
        return;
    }
    m_enableMenuSearch = enabled;
    removeSearchActionsFromMenu();
    Q_EMIT enableMenuSearchChanged();
    Q_EMIT modelNeedsUpdate();
}

bool AppMenuModel::menuAvailable() const
{
    return m_menuAvailable;
}

void AppMenuModel::setMenuAvailable(bool set)
{
    if (m_menuAvailable != set) {
        m_menuAvailable = set;
        setVisible(true);
        Q_EMIT menuAvailableChanged();
        Q_EMIT modelNeedsUpdate();
    }
}

bool AppMenuModel::allScreens() const
{
    return m_allScreens;
}

void AppMenuModel::setallScreens(bool allScreens)
{
    if (m_allScreens == allScreens) {
        return;
    }
    m_allScreens = allScreens;
    m_tasksModel->setFilterByScreen(!m_allScreens);
    Q_EMIT allScreensChanged();
}

bool AppMenuModel::visible() const
{
    return m_visible;
}

void AppMenuModel::setVisible(bool visible)
{
    if (m_visible != visible) {
        m_visible = visible;
        Q_EMIT visibleChanged();
    }
}

QRect AppMenuModel::screenGeometry() const
{
    return m_tasksModel->screenGeometry();
}

void AppMenuModel::setScreenGeometry(QRect geometry)
{
    m_tasksModel->setScreenGeometry(geometry);
}

// QAbstractListModel overrides

int AppMenuModel::rowCount(const QModelIndex& parent) const
{
    Q_UNUSED(parent);
    if (!m_menuAvailable || !m_menu) {
        return 0;
    }
    return m_menu->actions().count() + (m_enableMenuSearch && m_searchAction && !m_menu->isEmpty() ? 1 : 0);
}

// Search-action helpers (Wayland-only path)

void AppMenuModel::removeSearchActionsFromMenu()
{
    if (m_searchMenu) {
        for (auto action : std::as_const(m_currentSearchActions)) {
            if (action) {
                m_searchMenu->removeAction(action);
            }
        }
    }
    m_currentSearchActions.clear();
}

void AppMenuModel::insertSearchActionsIntoMenu(const QString& filter)
{
    removeSearchActionsFromMenu();
    if (filter.isEmpty() || !m_enableMenuSearch) {
        return;
    }
    const auto actions = flatActionList();
    for (const auto& action : actions) {
        if (QuickBarMenu::visibleMenuText(action->text()).contains(filter, Qt::CaseInsensitive)) {
            m_searchAction->menu()->addAction(action);
            m_currentSearchActions << action;
        }
    }
}

// Window / model refresh

void AppMenuModel::update()
{
    beginResetModel();
    endResetModel();
    m_updatePending = false;
}

void AppMenuModel::onActiveWindowChanged()
{
    const QModelIndex activeTaskIndex = m_tasksModel->activeTask();
    if (!activeTaskIndex.isValid() && m_containmentStatus == Plasma::Types::AcceptingInputStatus
        && (!m_genericMenu || m_genericTarget.isValid())) {
        return;
    }

    const QString objectPath = m_tasksModel->data(activeTaskIndex, TaskManager::AbstractTasksModel::ApplicationMenuObjectPath).toString();
    const QString serviceName = m_tasksModel->data(activeTaskIndex, TaskManager::AbstractTasksModel::ApplicationMenuServiceName).toString();
    updateApplicationMenu(serviceName, objectPath);
    if (serviceName.isEmpty() || objectPath.isEmpty()) updateGenericMenu();
    Q_EMIT activeAppNameChanged();
}

QHash<int, QByteArray> AppMenuModel::roleNames() const
{
    QHash<int, QByteArray> roleNames;
    roleNames[MenuRole] = QByteArrayLiteral("activeMenu");
    roleNames[ActionRole] = QByteArrayLiteral("activeActions");
    return roleNames;
}

QList<QAction*> AppMenuModel::flatActionList()
{
    QList<QAction*> ret;
    if (!m_menuAvailable || !m_menu) {
        return ret;
    }
    QSet<QMenu*> visited;
    QuickBarMenu::collectMenuActions(m_menu, ret, visited);
    return ret;
}

TaskManager::TasksModel* AppMenuModel::tasksModel() const
{
    return m_tasksModel;
}

QVariant AppMenuModel::data(const QModelIndex& index, int role) const
{
    if (!m_menuAvailable || !m_menu) {
        return {};
    }

    if (!index.isValid()) {
        if (role == MenuRole) {
            return QString();
        } else if (role == ActionRole) {
            return QVariant::fromValue(m_menu->menuAction());
        }
    }

    const auto actions = m_menu->actions();
    const int row = index.row();
    if (row == actions.count() && m_enableMenuSearch && m_searchAction) {
        if (role == MenuRole) {
            return m_searchAction->text();
        } else if (role == ActionRole) {
            return QVariant::fromValue(m_searchAction.data());
        }
    }
    if (row < 0 || row >= actions.count()) {
        return {};
    }

    if (role == MenuRole) {
        return actions.at(row)->text();
    } else if (role == ActionRole) {
        return QVariant::fromValue(actions.at(row));
    }

    return {};
}

// DBus importer attachment

/// Swap the watched dbus service / object. The old importer is
/// destroyed when ``m_importer`` is reassigned (unique_ptr); the new
/// one starts publishing via ``modelNeedsUpdate``.
void AppMenuModel::updateApplicationMenu(const QString& serviceName, const QString& menuObjectPath)
{
    if (serviceName.isEmpty() && menuObjectPath.isEmpty() && m_genericMenu
        && m_genericTarget.isValid() && m_genericTarget == m_tasksModel->activeTask() && m_enableGenericMenu) return;
    if (m_serviceName == serviceName && m_menuObjectPath == menuObjectPath && m_importer) {
        QMetaObject::invokeMethod(m_importer.get(), "updateMenu", Qt::QueuedConnection);
        return;
    }

    Q_EMIT menuSourceAboutToChange();

    // Do not expose the previous application's actions while the new menu is
    // loading. The importer deletes its QMenu asynchronously.
    removeSearchActionsFromMenu();
    m_menu.clear();
    m_genericMenu.reset();
    m_genericTarget = QPersistentModelIndex();
    ++m_shortcutGeneration;
    setMenuAvailable(false);
    Q_EMIT modelNeedsUpdate();

    if (serviceName.isEmpty() || menuObjectPath.isEmpty()) {
        setMenuAvailable(false);
        setVisible(false);
        m_serviceName = QString();
        m_menuObjectPath = QString();
        m_serviceWatcher->setWatchedServices({});
        m_importer.reset();
    } else {
        m_serviceName = serviceName;
        m_menuObjectPath = menuObjectPath;
        m_serviceWatcher->setWatchedServices(QStringList({m_serviceName}));

        m_importer = std::make_unique<KDBusMenuImporter>(serviceName, menuObjectPath);
        QMetaObject::invokeMethod(m_importer.get(), "updateMenu", Qt::QueuedConnection);

        connect(m_importer.get(), &DBusMenuImporter::menuUpdated, this, [=, this](QMenu* menu) {
            m_menu = m_importer->menu();
            if (m_menu.isNull() || menu != m_menu) {
                return;
            }

            if (m_menu->isEmpty()) {
                setMenuAvailable(false);
                updateGenericMenu();
                return;
            }
            if (m_genericMenu) {
                Q_EMIT menuSourceAboutToChange();
                removeSearchActionsFromMenu();
                m_genericMenu.reset();
                m_genericTarget = QPersistentModelIndex();
                ++m_shortcutGeneration;
            }
            setMenuAvailable(true);

            QMenu *windowView = nullptr;
            const auto viewLabel = i18n("&View").remove(QLatin1Char('&'));
            for (auto *action : m_menu->actions()) {
                const auto label = action->text().remove(QLatin1Char('&'));
                if (action->menu() && (label.compare(viewLabel, Qt::CaseInsensitive) == 0
                    || label.compare(QStringLiteral("View"), Qt::CaseInsensitive) == 0)) {
                    windowView = action->menu();
                    break;
                }
            }
            if (!windowView && m_tasksModel->activeTask().isValid()) {
                windowView = m_menu->addMenu(i18n("&View"));
                windowView->setProperty("tahoeLocalView", true);
            }
            if (windowView) windowView->setProperty("tahoeWindowView", true);

            const auto actions = m_menu->actions();
            for (QAction* a : actions) {
                connect(a, &QAction::changed, this, [this, a] {
                    if (m_menuAvailable && m_menu) {
                        const int actionIdx = m_menu->actions().indexOf(a);
                        if (actionIdx > -1) {
                            const QModelIndex modelIdx = index(actionIdx, 0);
                            Q_EMIT dataChanged(modelIdx, modelIdx);
                        }
                    }
                });
                connect(a, &QAction::destroyed, this, &AppMenuModel::modelNeedsUpdate);

                if (a->menu() && !a->menu()->property("tahoeLocalView").toBool()) {
                    m_importer->updateMenu(a->menu());
                }
            }

            setMenuAvailable(true);
            Q_EMIT modelNeedsUpdate();
        });

        connect(m_importer.get(), &DBusMenuImporter::actionActivationRequested, this, [this](QAction* action) {
            if (!m_menuAvailable || !m_menu) {
                return;
            }
            const auto actions = m_menu->actions();
            auto it = std::find(actions.begin(), actions.end(), action);
            if (it != actions.end()) {
                Q_EMIT requestActivateIndex(it - actions.begin());
            }
        });

        setVisible(true);
        Q_EMIT modelNeedsUpdate();
    }
}


bool AppMenuModel::enableGenericMenu() const { return m_enableGenericMenu; }
void AppMenuModel::setEnableGenericMenu(bool enabled)
{
    if (m_enableGenericMenu == enabled) return;
    m_enableGenericMenu = enabled;
    if (!enabled && m_genericMenu) {
        Q_EMIT menuSourceAboutToChange();
        removeSearchActionsFromMenu();
        m_menu.clear();
        m_genericMenu.reset();
        m_genericTarget = QPersistentModelIndex();
        ++m_shortcutGeneration;
        setMenuAvailable(false);
    }
    onActiveWindowChanged();
    Q_EMIT enableGenericMenuChanged();
}

void AppMenuModel::sendGenericShortcut(const QKeySequence &sequence, const QPersistentModelIndex &target)
{
    const quint64 generation = ++m_shortcutGeneration;
    // Let QMenu release its input grab before restoring the originating window.
    QTimer::singleShot(0, this, [this, target, sequence, generation] {
        if (!target.isValid() || target != m_genericTarget || generation != m_shortcutGeneration) return;
        const auto active = m_tasksModel->activeTask();
        if (active.isValid() && active != target) return;
        m_tasksModel->requestActivate(target);
        QTimer::singleShot(100, this, [this, target, sequence, generation] {
            if (generation != m_shortcutGeneration || !target.isValid()
                || target != m_genericTarget || target != m_tasksModel->activeTask()) return;
            m_shortcutSender->send(sequence);
        });
    });
}

void AppMenuModel::updateGenericMenu()
{
    const QPersistentModelIndex target(m_tasksModel->activeTask());
    if (!m_enableGenericMenu || !target.isValid()
        || !target.data(TaskManager::AbstractTasksModel::IsWindow).toBool()) return;
    if (m_genericMenu && m_genericTarget == target) {
        m_menu = m_genericMenu.get();
        setMenuAvailable(true);
        setVisible(true);
        return;
    }
    Q_EMIT menuSourceAboutToChange();
    removeSearchActionsFromMenu();
    m_menu.clear();
    m_genericMenu = std::make_unique<QMenu>();
    m_genericTarget = target;
    ++m_shortcutGeneration;
    m_genericMenu->setObjectName(QStringLiteral("tahoe-generic-menu"));
    auto *edit = m_genericMenu->addMenu(i18n("&Edit"));
    auto addShortcut = [this, edit, target](const QString &label, QKeySequence::StandardKey key) {
        auto *action = edit->addAction(label);
        action->setShortcut(QKeySequence(key));
        action->setEnabled(m_shortcutSender->available());
        connect(action, &QAction::triggered, this, [this, target, sequence = action->shortcut()] {
            sendGenericShortcut(sequence, target);
        });
    };
    addShortcut(i18n("&Undo"), QKeySequence::Undo);
    addShortcut(i18n("&Redo"), QKeySequence::Redo);
    edit->addSeparator();
    addShortcut(i18n("Cu&t"), QKeySequence::Cut);
    addShortcut(i18n("&Copy"), QKeySequence::Copy);
    addShortcut(i18n("&Paste"), QKeySequence::Paste);
    edit->addSeparator();
    addShortcut(i18n("Select &All"), QKeySequence::SelectAll);
    auto *view = m_genericMenu->addMenu(i18n("&View"));
    view->setProperty("tahoeWindowView", true);
    refreshWindowActions(view);
    m_menu = m_genericMenu.get();
    setMenuAvailable(true);
    setVisible(true);
    Q_EMIT modelNeedsUpdate();
}

void AppMenuModel::refreshWindowActions(QMenu *menu)
{
    // Only replace our own additions; imported application actions stay intact.
    for (auto *action : menu->actions()) {
        if (action->property("tahoeWindowAction").toBool()) delete action;
    }
    const QPersistentModelIndex target(m_tasksModel->activeTask());
    if (!target.isValid()) return;
    using Roles = TaskManager::AbstractTasksModel;
    if (!menu->isEmpty()) {
        auto *separator = menu->addSeparator();
        separator->setProperty("tahoeWindowAction", true);
    }
    auto add = [this, menu, target](const QString &label, int capability, auto request) {
        auto *action = menu->addAction(label);
        action->setProperty("tahoeWindowAction", true);
        action->setEnabled(target.data(capability).toBool());
        connect(action, &QAction::triggered, this, [this, target, request] {
            if (target.isValid()) (m_tasksModel->*request)(target);
        });
    };
    add(i18n("Close Window"), Roles::IsClosable, &TaskManager::TasksModel::requestClose);
    add(i18n("Minimize"), Roles::IsMinimizable, &TaskManager::TasksModel::requestToggleMinimized);
    add(target.data(Roles::IsMaximized).toBool() ? i18n("Restore") : i18n("Zoom"),
        Roles::IsMaximizable, &TaskManager::TasksModel::requestToggleMaximized);
    add(target.data(Roles::IsFullScreen).toBool() ? i18n("Exit Full Screen") : i18n("Enter Full Screen"),
        Roles::IsFullScreenable, &TaskManager::TasksModel::requestToggleFullScreen);
}

#include "moc_appmenumodel.cpp"
