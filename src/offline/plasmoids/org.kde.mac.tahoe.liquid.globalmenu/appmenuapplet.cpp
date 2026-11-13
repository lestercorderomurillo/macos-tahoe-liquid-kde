/*
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-FileCopyrightText: 2026 QuickBar contributors
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#include "appmenuapplet.h"
#include "appmenumodel.h"
#include "systemmenustyle.h"

#include <KColorScheme>
#include <KLocalizedString>
#include <KUser>
#include <QAction>
#include <QApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QKeyEvent>
#include <QMenu>
#include <QFileInfo>
#include <QPersistentModelIndex>
#include <QStandardPaths>
#include <QTimer>
#include <KDesktopFile>
#include <QLineEdit>
#include <QMouseEvent>
#include <QProcess>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScreen>
#include <QStandardPaths>
#include <QStyleOptionMenuItem>
#include <QTimer>
#include <abstracttasksmodel.h>

// File-scope state

int AppMenuApplet::s_refs = 0;

namespace {
/// DBus name we register as while at least one AppMenuApplet is alive.
/// Other system pieces (Latte, Plank, etc.) listen for this to know a
/// global menu view is on screen and suppress their own in-window menubar.
QString viewService()
{
    return QStringLiteral("org.kde.kappmenuview");
}

/// Force a menu to follow the ACTIVE KDE colour scheme (light/dark).
///
/// The system / window menus are plain QWidget QMenus, so they inherit
/// plasmashell's widget-style palette (Kvantum). Kvantum does not hot-reload
/// its kvconfig, so after a live light↔dark switch a freshly-opened menu can
/// still paint with the previous mode's palette — the "About This Computer"
/// popup staying light in dark mode. KColorScheme reads the scheme from
/// kdeglobals on disk (always current), so applying it here makes the menu
/// track the mode regardless of what the running widget style cached. Safe:
/// it only sets this widget's palette, touches nothing global, and needs no
/// plasmashell restart.
void applyActiveColorScheme(QWidget* menu)
{
    if (!menu) {
        return;
    }
    QPalette pal = menu->palette();
    const KColorScheme window(QPalette::Active, KColorScheme::Window);
    const KColorScheme view(QPalette::Active, KColorScheme::View);
    pal.setBrush(QPalette::Window, window.background());
    pal.setBrush(QPalette::WindowText, window.foreground());
    pal.setBrush(QPalette::Base, view.background());
    pal.setBrush(QPalette::Text, view.foreground());
    pal.setBrush(QPalette::ButtonText, window.foreground());
    const KColorScheme selection(QPalette::Active, KColorScheme::Selection);
    pal.setBrush(QPalette::Highlight, selection.background());
    pal.setBrush(QPalette::HighlightedText, selection.foreground());
    menu->setPalette(pal);
}
} // namespace

// Lifecycle

/// Bump the global refcount and (re)register the kappmenuview service
/// on first instance. The Plasma::Applet ``destroyedChanged`` is
/// observed so deferred destruction (right-click → remove widget then
/// drag back) still keeps the service in sync.
AppMenuApplet::AppMenuApplet(QObject* parent, const KPluginMetaData& data, const QVariantList& args)
    : Plasma::Applet(parent, data, args)
{
    ++s_refs;
    if (s_refs == 1) {
        QDBusConnection::sessionBus().interface()->registerService(
            viewService(), QDBusConnectionInterface::QueueService, QDBusConnectionInterface::DontAllowReplacement);
    }
    connect(this, &Applet::destroyedChanged, this, [this](bool destroyed) {
        m_registered = !destroyed;
        if (destroyed) {
            if (--s_refs == 0) {
                QDBusConnection::sessionBus().interface()->unregisterService(viewService());
            }
        } else {
            if (++s_refs == 1) {
                QDBusConnection::sessionBus().interface()->registerService(
                    viewService(), QDBusConnectionInterface::QueueService, QDBusConnectionInterface::DontAllowReplacement);
            }
        }
    });
}

AppMenuApplet::~AppMenuApplet()
{
    // Plasma destroys the QML model in its base destructor, after our menu state.
    if (m_model) {
        disconnect(m_model, nullptr, this, nullptr);
    }
    resetApplicationMenu();
    if (m_ownsCurrentMenu && m_currentMenu) {
        delete m_currentMenu.data();
    }
    delete m_systemMenu.data();
    if (m_registered && --s_refs == 0) {
        QDBusConnection::sessionBus().interface()->unregisterService(viewService());
    }
}

// Adapted from QuickBar's owned-proxy/borrowed-menu lifecycle, preserving
// Tahoe's AboutToShow refresh and its persistent Wayland popup grab.
void AppMenuApplet::restoreBorrowedActions()
{
    if (!m_ownsCurrentMenu || !m_currentMenu) {
        return;
    }
    auto* menuAction = m_currentMenu->menuAction();
    for (auto* action : m_currentMenu->actions()) {
        if (action->menu() && action->menu() != m_currentMenu) {
            action->menu()->hide();
        }
        m_currentMenu->removeAction(action);
        if (m_sourceMenu) {
            m_sourceMenu->addAction(action);
        }
    }
    if (m_sourceMenu) {
        menuAction->setMenu(m_sourceMenu);
    }
}

void AppMenuApplet::resetApplicationMenu()
{
    if (m_currentMenu) {
        m_currentMenu->hide();
        m_currentMenu->removeEventFilter(this);
    }
    restoreBorrowedActions();
    m_sourceMenu.clear();
    if (!m_ownsCurrentMenu) {
        m_currentMenu.clear();
    }
    setCurrentIndex(-1);
}

void AppMenuApplet::init() { }

// Property accessors

QAbstractItemModel* AppMenuApplet::model() const
{
    return m_model;
}

void AppMenuApplet::setModel(QAbstractItemModel* model)
{
    if (m_model != model) {
        resetApplicationMenu();
        if (m_model) {
            disconnect(m_model, nullptr, this, nullptr);
        }
        m_model = model;
        if (m_model) {
            if (auto* appModel = qobject_cast<AppMenuModel*>(m_model)) {
                connect(appModel, &AppMenuModel::menuSourceAboutToChange, this, &AppMenuApplet::resetApplicationMenu);
            } else {
                connect(m_model, &QAbstractItemModel::modelAboutToBeReset, this, &AppMenuApplet::resetApplicationMenu);
            }
            connect(m_model, &QObject::destroyed, this, &AppMenuApplet::resetApplicationMenu);
        }
        Q_EMIT modelChanged();
    }
}

int AppMenuApplet::view() const
{
    return m_viewType;
}

void AppMenuApplet::setView(int type)
{
    if (m_viewType != type) {
        resetApplicationMenu();
        m_viewType = type;
        Q_EMIT viewChanged();
    }
}

int AppMenuApplet::currentIndex() const
{
    return m_currentIndex;
}

void AppMenuApplet::setCurrentIndex(int currentIndex)
{
    if (m_currentIndex != currentIndex) {
        m_currentIndex = currentIndex;
        Q_EMIT currentIndexChanged();
    }
}

QQuickItem* AppMenuApplet::buttonGrid() const
{
    return m_buttonGrid;
}

void AppMenuApplet::setButtonGrid(QQuickItem* buttonGrid)
{
    if (m_buttonGrid != buttonGrid) {
        m_buttonGrid = buttonGrid;
        Q_EMIT buttonGridChanged();
    }
}

// Menu construction + popup management

QMenu* AppMenuApplet::createMenu(int idx) const
{
    if (!m_model || idx < 0 || idx >= m_model->rowCount()) {
        return nullptr;
    }
    QMenu* menu = nullptr;

    if (view() == CompactView) {
        if (auto* menuAction = m_model->data(QModelIndex(), AppMenuModel::ActionRole).value<QAction*>()) {
            menu = menuAction->menu();
        }
    } else if (view() == FullView) {
        const QModelIndex index = m_model->index(idx, 0);
        if (auto* action = m_model->data(index, AppMenuModel::ActionRole).value<QAction*>()) {
            menu = action->menu();
        }
    }

    if (menu && menu->property("tahoeWindowView").toBool()) {
        if (auto *model = qobject_cast<AppMenuModel*>(m_model))
            model->refreshWindowActions(menu);
    }
    return menu;
}

void AppMenuApplet::onMenuAboutToHide()
{
    if (m_sourceMenu && m_sourceMenu != m_currentMenu) {
        Q_EMIT m_sourceMenu->aboutToHide();
    }
    restoreBorrowedActions();
    setCurrentIndex(-1);
}

/// Map Plasma's panel location to the QMenu popup-anchoring edge so the
/// menu opens "out from" the panel (top panel → menu drops down, left
/// panel → menu opens to the right, etc.).
Qt::Edges edgeFromLocation(Plasma::Types::Location location)
{
    switch (location) {
    case Plasma::Types::TopEdge:
        return Qt::TopEdge;
    case Plasma::Types::BottomEdge:
        return Qt::BottomEdge;
    case Plasma::Types::LeftEdge:
        return Qt::LeftEdge;
    case Plasma::Types::RightEdge:
        return Qt::RightEdge;
    case Plasma::Types::Floating:
    case Plasma::Types::Desktop:
    case Plasma::Types::FullScreen:
        break;
    }
    return {};
}

// QML-triggered popups

void AppMenuApplet::trigger(QQuickItem* ctx, int idx)
{
    if (!m_model || idx < 0 || idx >= m_model->rowCount()) {
        return;
    }
    auto* selectedAction = m_model->index(idx, 0).data(AppMenuModel::ActionRole).value<QAction*>();
    if (view() == FullView && (!selectedAction || !selectedAction->isEnabled() || !selectedAction->isVisible())) {
        return;
    }
    if (m_currentIndex == idx) {
        return;
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen()) {
        return;
    }

    if (QMenu* actionMenu = createMenu(idx)) {
        showMenu(ctx, actionMenu, idx);
    } else if (selectedAction) {
        selectedAction->trigger();
    }
}

void AppMenuApplet::showMenu(QQuickItem* ctx, QMenu* actionMenu, int idx)
{
    auto ungrabMouseHack = [ctx]() {
        if (ctx && ctx->window() && ctx->window()->mouseGrabberItem()) {
            ctx->window()->mouseGrabberItem()->ungrabMouse();
        }
    };

    if (view() == FullView) {
        if (!m_currentMenu || !m_ownsCurrentMenu) {
            m_currentMenu = new QMenu;
            m_ownsCurrentMenu = true;
            connect(m_currentMenu, &QMenu::aboutToHide, this, &AppMenuApplet::onMenuAboutToHide, Qt::UniqueConnection);
        } else if (m_sourceMenu != actionMenu) {
            if (m_sourceMenu) {
                Q_EMIT m_sourceMenu->aboutToHide();
            }
            restoreBorrowedActions();
        }
        m_currentMenu->setActiveAction(nullptr);
        m_currentMenu->setStyle(actionMenu->style());
        m_currentMenu->setPalette(actionMenu->palette());
        m_currentMenu->setFont(actionMenu->font());
        m_sourceMenu = actionMenu;
        auto menuAction = m_sourceMenu->menuAction();
        for (QAction* action : m_sourceMenu->actions()) {
            m_sourceMenu->removeAction(action);
            m_currentMenu->addAction(action);
        }
        menuAction->setMenu(m_currentMenu);
        // Keep one popup and Wayland grab across Apple, app name and File/Edit.
        // Notify the imported menu on every selection so its D-Bus
        // AboutToShow handler refreshes dynamic application actions.
        Q_EMIT m_sourceMenu->aboutToShow();
    } else {
        restoreBorrowedActions();
        if (m_ownsCurrentMenu && m_currentMenu) {
            delete m_currentMenu.data();
        }
        m_ownsCurrentMenu = false;
        m_currentMenu = actionMenu;
        m_sourceMenu = actionMenu;
    }

    QTimer::singleShot(0, ctx, ungrabMouseHack);

    const auto& geo = ctx->window()->screen()->availableVirtualGeometry();
    QPoint pos = ctx->window()->mapToGlobal(ctx->mapToScene(QPointF()).toPoint());

    const Qt::Edges edges = edgeFromLocation(location());
    m_currentMenu->setProperty("_breeze_menu_seamless_edges", QVariant::fromValue(edges));

    if (location() == Plasma::Types::TopEdge) {
        pos.setY(pos.y() + ctx->height());
    }

    m_currentMenu->adjustSize();
    pos = QPoint(qBound(geo.x(), pos.x(), geo.x() + geo.width() - m_currentMenu->width()),
        qBound(geo.y(), pos.y(), geo.y() + geo.height() - m_currentMenu->height()));

    if (view() == FullView) {
        if (m_currentMenu->isVisible()) {
            m_currentMenu->move(pos);
        } else {
            m_currentMenu->installEventFilter(this);
            m_currentMenu->winId();
            m_currentMenu->windowHandle()->setTransientParent(ctx->window());
            m_currentMenu->popup(pos);
        }
    } else if (view() == CompactView) {
        if (m_currentMenu->isEmpty()) {
            return;
        }
        m_currentMenu->installEventFilter(this);
        m_currentMenu->popup(pos);
        connect(actionMenu, &QMenu::aboutToHide, this, &AppMenuApplet::onMenuAboutToHide, Qt::UniqueConnection);
    }

    setCurrentIndex(idx);
}

void AppMenuApplet::triggerWindowMenu(QQuickItem* ctx)
{
    static constexpr int WINDOW_MENU_INDEX = -2;

    if (m_currentIndex == WINDOW_MENU_INDEX) {
        return;
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen()) {
        return;
    }

    auto* appModel = qobject_cast<AppMenuModel*>(m_model.data());
    if (!appModel) {
        return;
    }

    auto* tasks = appModel->tasksModel();
    const QPersistentModelIndex activeTask(tasks->activeTask());
    if (!activeTask.isValid()) {
        return;
    }

    if (!m_windowMenu) {
        m_windowMenu = std::make_unique<QMenu>();
    }
    m_windowMenu->clear();
    // Reused across light↔dark switches, so refresh the palette on every open.
    applyActiveColorScheme(m_windowMenu.get());

    // Read metadata only. Never execute an application's binary or Exec entry
    // to discover its version, and never expose process command-line arguments.
    QVariantMap info;
    info.insert(QStringLiteral("name"), activeTask.data(TaskManager::AbstractTasksModel::AppName));
    info.insert(QStringLiteral("description"), activeTask.data(TaskManager::AbstractTasksModel::GenericName));
    info.insert(QStringLiteral("applicationId"), activeTask.data(TaskManager::AbstractTasksModel::AppId));
    info.insert(QStringLiteral("icon"), activeTask.data(Qt::DecorationRole));
    const auto pid = activeTask.data(TaskManager::AbstractTasksModel::AppPid).toLongLong();
    if (pid > 0) {
        info.insert(QStringLiteral("processId"), QString::number(pid));
        info.insert(QStringLiteral("executable"), QFileInfo(QStringLiteral("/proc/%1/exe").arg(pid)).symLinkTarget());
    }
    auto launcher = activeTask.data(TaskManager::AbstractTasksModel::LauncherUrlWithoutIcon).toUrl();
    if (launcher.isEmpty()) launcher = activeTask.data(TaskManager::AbstractTasksModel::LauncherUrl).toUrl();
    QString desktopPath;
    if (launcher.isLocalFile()) {
        desktopPath = launcher.toLocalFile();
    } else if (launcher.scheme() == QLatin1String("applications")) {
        const QString name = launcher.path();
        if (!name.contains(QLatin1Char('/')) && name.endsWith(QLatin1String(".desktop")))
            desktopPath = QStandardPaths::locate(QStandardPaths::GenericDataLocation, QStringLiteral("applications/") + name);
    }
    if (desktopPath.endsWith(QLatin1String(".desktop")) && QFileInfo(desktopPath).isFile()) {
        KDesktopFile desktop(desktopPath);
        info.insert(QStringLiteral("desktopFile"), desktopPath);
        if (info.value(QStringLiteral("name")).toString().isEmpty()) info.insert(QStringLiteral("name"), desktop.readName());
        if (info.value(QStringLiteral("description")).toString().isEmpty()) info.insert(QStringLiteral("description"), desktop.readGenericName());
        if (qvariant_cast<QIcon>(info.value(QStringLiteral("icon"))).isNull())
            info.insert(QStringLiteral("icon"), QIcon::fromTheme(desktop.readIcon()));
    }
    if (info.value(QStringLiteral("name")).toString().isEmpty())
        info.insert(QStringLiteral("name"), info.value(QStringLiteral("applicationId")));
    if (info.value(QStringLiteral("name")).toString().isEmpty())
        info.insert(QStringLiteral("name"), i18n("Application"));
    if (qvariant_cast<QIcon>(info.value(QStringLiteral("icon"))).isNull())
        info.insert(QStringLiteral("icon"), QIcon::fromTheme(QStringLiteral("application-x-executable")));

    auto *aboutAction = m_windowMenu->addAction(i18n("About %1", QString(info.value(QStringLiteral("name")).toString()).replace(QLatin1Char('&'), QStringLiteral("&&"))));
    connect(aboutAction, &QAction::triggered, this, [this, activeTask, info] {
        if (!activeTask.isValid()) return;
        // Release the popup grab before the independent About window opens.
        QTimer::singleShot(0, this, [this, info] { Q_EMIT applicationAboutRequested(info); });
    });
    auto* closeAction = m_windowMenu->addAction(i18n("Close %1", QString(info.value(QStringLiteral("name")).toString()).replace(QLatin1Char('&'), QStringLiteral("&&"))));
    closeAction->setEnabled(tasks->data(activeTask, TaskManager::AbstractTasksModel::IsClosable).toBool());
    connect(closeAction, &QAction::triggered, tasks, [tasks, activeTask]() {
        if (activeTask.isValid()) tasks->requestClose(activeTask);
    });

    showMenu(ctx, m_windowMenu.get(), WINDOW_MENU_INDEX);
}

static void runCommand(const QString& cmd)
{
    QProcess::startDetached(QStringLiteral("/bin/sh"), {QStringLiteral("-c"), cmd});
}

static bool isLegacyDBusCommand(const QString& command,
                                const QString& service,
                                const QString& path,
                                const QString& interface,
                                const QString& method)
{
    const QStringList clients = {
        QStringLiteral("qdbus6"),
        QStringLiteral("qdbus-qt6"),
        QStringLiteral("qdbus"),
    };
    const QStringList calls = command.split(QStringLiteral("||"), Qt::SkipEmptyParts);
    if (calls.isEmpty()) {
        return false;
    }
    for (const QString& rawCall : calls) {
        const QString call = rawCall.simplified();
        bool matches = false;
        for (const QString& client : clients) {
            const QString prefix = QStringLiteral("%1 %2 %3 ").arg(client, service, path);
            if (call == prefix + method || call == prefix + interface + QLatin1Char('.') + method) {
                matches = true;
                break;
            }
        }
        if (!matches) {
            return false;
        }
    }
    return true;
}

static void callSessionDBus(const QString& service,
                            const QString& path,
                            const QString& interface,
                            const QString& method)
{
    QTimer::singleShot(0, qApp, [service, path, interface, method]() {
        const QDBusMessage message = QDBusMessage::createMethodCall(
            service, path, interface, method);
        QDBusConnection::sessionBus().asyncCall(message);
    });
}

static void runSystemAction(const QString& configuredCommand,
                            const QString& service,
                            const QString& path,
                            const QString& interface,
                            const QString& method)
{
    // Older releases stored qdbus shell commands as the defaults.  Invoke the
    // same methods through QtDBus instead: Fedora names the client qdbus-qt6,
    // while Arch names it qdbus6, and neither executable is needed in-process.
    // Queue the call so QMenu can release its grabs before a confirmation dialog
    // appears.  A genuinely customized command remains an explicit user override.
    if (configuredCommand.trimmed().isEmpty()
        || isLegacyDBusCommand(configuredCommand, service, path, interface, method)) {
        callSessionDBus(service, path, interface, method);
        return;
    }
    runCommand(configuredCommand);
}

static void runSuspendAction(const QString& configuredCommand)
{
    const QString service = QStringLiteral("org.kde.Solid.PowerManagement");
    const QString path = QStringLiteral(
        "/org/kde/Solid/PowerManagement/Actions/SuspendSession");
    const QString interface = QStringLiteral(
        "org.kde.Solid.PowerManagement.Actions.SuspendSession");
    const QString method = QStringLiteral("suspendToRam");

    // Plasma 6 moved suspend off the PowerManagement root object. Recognize
    // both the current built-in command and our pre-v0.49.2 default so an old
    // applet configuration migrates without executing a dead shell command.
    const bool oldDefault = isLegacyDBusCommand(
        configuredCommand,
        service,
        QStringLiteral("/org/kde/Solid/PowerManagement"),
        service,
        QStringLiteral("requestSuspend"));
    if (configuredCommand.trimmed().isEmpty() || oldDefault
        || isLegacyDBusCommand(configuredCommand, service, path, interface, method)) {
        callSessionDBus(service, path, interface, method);
        return;
    }
    runCommand(configuredCommand);
}

void AppMenuApplet::triggerSystemMenu(QQuickItem* ctx)
{
    static constexpr int SYSTEM_MENU_INDEX = -3;

    if (m_currentIndex == SYSTEM_MENU_INDEX) {
        return;
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen()) {
        return;
    }

    if (!m_systemMenu) {
        m_systemMenu = new QMenu;
        QFont menuFont = QApplication::font("QMenu");
        menuFont.setWeight(QFont::Normal);
        m_systemMenu->setFont(menuFont);
        m_systemMenu->setStyle(new SystemMenuStyle(m_systemMenu));
    }
    auto* menu = m_systemMenu.data();
    menu->clear();
    applyActiveColorScheme(menu);

    const auto cfg = config();

    const auto preset = SystemMenuStyle::themePreset();
    static_cast<SystemMenuStyle*>(menu->style())->setPreset(preset);
    auto icon = [&cfg, preset](const char* key, const QString& fallback) {
        return SystemMenuStyle::menuIcon(cfg.readEntry(key, fallback), fallback, preset);
    };

    menu->addAction(icon("iconAbout", QStringLiteral("computer")), i18n("About This Computer"), this, [this]() { Q_EMIT aboutRequested(); });

    menu->addSeparator();

    menu->addAction(icon("iconSystemSettings", QStringLiteral("preferences-system")), i18n("System Settings…"),
        []() { runCommand(QStringLiteral("systemsettings")); });
    if (!QStandardPaths::findExecutable(QStringLiteral("plasma-discover")).isEmpty()) {
        menu->addAction(icon("iconAppStore", QStringLiteral("software-store-symbolic")), i18n("App Store…"),
            []() { runCommand(QStringLiteral("plasma-discover")); });
    }

    menu->addSeparator();

    menu->addAction(icon("iconForceQuit", QStringLiteral("dialog-cancel")), i18n("Force Quit…"),
        []() { runCommand(QStringLiteral("qdbus6 org.kde.KWin /KWin slotKillWindow || xkill")); });

    menu->addSeparator();

    menu->addAction(icon("iconSleep", QStringLiteral("system-suspend")), i18n("Sleep"),
        [cmd = cfg.readEntry(
             "cmdSleep", QStringLiteral("qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/Actions/SuspendSession org.kde.Solid.PowerManagement.Actions.SuspendSession.suspendToRam || qdbus-qt6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/Actions/SuspendSession org.kde.Solid.PowerManagement.Actions.SuspendSession.suspendToRam || qdbus org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/Actions/SuspendSession org.kde.Solid.PowerManagement.Actions.SuspendSession.suspendToRam"))]() {
            runSuspendAction(cmd);
        });
    menu->addAction(icon("iconRestart", QStringLiteral("system-reboot")), i18n("Restart…"),
        [cmd = cfg.readEntry("cmdRestart", QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptReboot"))]() {
            runSystemAction(cmd,
                QStringLiteral("org.kde.LogoutPrompt"),
                QStringLiteral("/LogoutPrompt"),
                QStringLiteral("org.kde.LogoutPrompt"),
                QStringLiteral("promptReboot"));
        });
    menu->addAction(icon("iconShutDown", QStringLiteral("system-shutdown")), i18n("Shut Down…"),
        [cmd = cfg.readEntry("cmdShutDown", QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"))]() {
            runSystemAction(cmd,
                QStringLiteral("org.kde.LogoutPrompt"),
                QStringLiteral("/LogoutPrompt"),
                QStringLiteral("org.kde.LogoutPrompt"),
                QStringLiteral("promptShutDown"));
        });

    menu->addSeparator();

    auto* lockAction = menu->addAction(icon("iconLockScreen", QStringLiteral("system-lock-screen")), i18n("Lock Screen"),
        [cmd = cfg.readEntry("cmdLockScreen", QStringLiteral("qdbus6 org.freedesktop.ScreenSaver /ScreenSaver Lock || loginctl lock-session"))]() {
            runCommand(cmd);
        });
    lockAction->setShortcut(QKeySequence(Qt::CTRL | Qt::META | Qt::Key_Q));
    lockAction->setShortcutContext(Qt::WidgetShortcut);
    const QString firstName = KUser().property(KUser::FullName).toString().section(QLatin1Char(' '), 0, 0);
    auto* logoutAction = menu->addAction(icon("iconLogOut", QStringLiteral("user-identity")), i18n("Log Out %1…", firstName),
        [cmd = cfg.readEntry("cmdLogOut", QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptLogout"))]() {
            runSystemAction(cmd,
                QStringLiteral("org.kde.LogoutPrompt"),
                QStringLiteral("/LogoutPrompt"),
                QStringLiteral("org.kde.LogoutPrompt"),
                QStringLiteral("promptLogout"));
        });
    logoutAction->setShortcut(QKeySequence(Qt::SHIFT | Qt::META | Qt::Key_Q));
    logoutAction->setShortcutContext(Qt::WidgetShortcut);

    showMenu(ctx, menu, SYSTEM_MENU_INDEX);
}

// Keyboard event hookup

bool AppMenuApplet::eventFilter(QObject* watched, QEvent* event)
{
    auto* menu = qobject_cast<QMenu*>(watched);
    if (!menu) {
        return false;
    }

    if (event->type() == QEvent::KeyPress) {
        auto* e = static_cast<QKeyEvent*>(event);
        // QMenu owns the keyboard grab; widget shortcuts on borrowed actions
        // are not reliably dispatched by Qt's window shortcut map.
        if (m_currentIndex == -3) {
            const QKeySequence pressed(e->keyCombination());
            for (auto* action : menu->actions()) {
                if (action->isEnabled() && action->isVisible() && !action->shortcut().isEmpty()
                    && action->shortcut().matches(pressed) == QKeySequence::ExactMatch) {
                    if (!e->isAutoRepeat()) {
                        menu->hide();
                        action->trigger();
                    }
                    return true;
                }
            }
        }
        if (auto* field = qobject_cast<QLineEdit*>(QApplication::focusWidget());
            field && menu->isAncestorOf(field)
            && (e->key() == Qt::Key_Left || e->key() == Qt::Key_Right)) {
            return false;
        }

        if (e->key() == Qt::Key_Left) {
            if (m_currentIndex == -3) {
                return true;
            }
            int desiredIndex;
            if (m_currentIndex == -2) {
                desiredIndex = -3;
            } else if (m_currentIndex == 0) {
                desiredIndex = -2;
            } else {
                desiredIndex = m_currentIndex - 1;
            }
            Q_EMIT requestActivateIndex(desiredIndex);
            return true;
        } else if (e->key() == Qt::Key_Right) {
            if (menu->activeAction() && menu->activeAction()->menu()) {
                return false;
            }
            int desiredIndex;
            if (m_currentIndex == -3) {
                desiredIndex = -2;
            } else if (m_currentIndex == -2) {
                desiredIndex = 0;
            } else {
                desiredIndex = m_currentIndex + 1;
            }
            Q_EMIT requestActivateIndex(desiredIndex);
            return true;
        }

    } else if (event->type() == QEvent::MouseMove) {
        if (!config().group(QStringLiteral("Appearance")).readEntry("hoverOpensMenu", true)) {
            return false;
        }
        auto* e = static_cast<QMouseEvent*>(event);

        if (!m_buttonGrid || !m_buttonGrid->window()) {
            return false;
        }

        const QPointF& windowLocalPos = m_buttonGrid->window()->mapFromGlobal(e->globalPosition());
        if (auto* viewport = m_buttonGrid->parentItem(); viewport && viewport->clip()
            && !viewport->contains(viewport->mapFromScene(windowLocalPos))) {
            return false;
        }
        const QPointF& buttonGridLocalPos = m_buttonGrid->mapFromScene(windowLocalPos);
        auto* item = m_buttonGrid->childAt(buttonGridLocalPos.x(), buttonGridLocalPos.y());
        if (!item) {
            return false;
        }

        bool ok;
        const int buttonIndex = item->property("buttonIndex").toInt(&ok);
        if (!ok) {
            return false;
        }

        if (buttonIndex != m_currentIndex) {
            Q_EMIT requestActivateIndex(buttonIndex);
        }
        // QMenu must not process the old popup's mouse event after a switch.
        return true;
    }

    return false;
}

K_PLUGIN_CLASS_WITH_JSON(AppMenuApplet, "metadata.json")

#include "appmenuapplet.moc"
#include "moc_appmenuapplet.cpp"
