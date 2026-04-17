/*
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#include "appmenuapplet.h"
#include "appmenumodel.h"

#include <abstracttasksmodel.h>
#include <KUser>
#include <QAction>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QKeyEvent>
#include <QMenu>
#include <QMouseEvent>
#include <QProcess>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>

int AppMenuApplet::s_refs = 0;
namespace
{
QString viewService()
{
    return QStringLiteral("org.kde.kappmenuview");
}
}

AppMenuApplet::AppMenuApplet(QObject *parent, const KPluginMetaData &data, const QVariantList &args)
    : Plasma::Applet(parent, data, args)
{
    ++s_refs;
    if (s_refs == 1) {
        QDBusConnection::sessionBus().interface()->registerService(viewService(),
                                                                   QDBusConnectionInterface::QueueService,
                                                                   QDBusConnectionInterface::DontAllowReplacement);
    }
    connect(this, &Applet::destroyedChanged, this, [](bool destroyed) {
        if (destroyed) {
            if (--s_refs == 0) {
                QDBusConnection::sessionBus().interface()->unregisterService(viewService());
            }
        } else {
            if (++s_refs == 1) {
                QDBusConnection::sessionBus().interface()->registerService(viewService(),
                                                                           QDBusConnectionInterface::QueueService,
                                                                           QDBusConnectionInterface::DontAllowReplacement);
            }
        }
    });
}

AppMenuApplet::~AppMenuApplet() = default;

void AppMenuApplet::init()
{
}

QAbstractItemModel *AppMenuApplet::model() const
{
    return m_model;
}

void AppMenuApplet::setModel(QAbstractItemModel *model)
{
    if (m_model != model) {
        m_model = model;
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

QQuickItem *AppMenuApplet::buttonGrid() const
{
    return m_buttonGrid;
}

void AppMenuApplet::setButtonGrid(QQuickItem *buttonGrid)
{
    if (m_buttonGrid != buttonGrid) {
        m_buttonGrid = buttonGrid;
        Q_EMIT buttonGridChanged();
    }
}

QMenu *AppMenuApplet::createMenu(int idx) const
{
    QMenu *menu = nullptr;

    if (view() == CompactView) {
        if (auto *menuAction = m_model->data(QModelIndex(), AppMenuModel::ActionRole).value<QAction *>()) {
            menu = menuAction->menu();
        }
    } else if (view() == FullView) {
        const QModelIndex index = m_model->index(idx, 0);
        if (auto *action = m_model->data(index, AppMenuModel::ActionRole).value<QAction *>()) {
            menu = action->menu();
        }
    }

    return menu;
}

void AppMenuApplet::onMenuAboutToHide()
{
    auto menuAction = m_currentMenu->menuAction();
    menuAction->setMenu(m_sourceMenu);
    setCurrentIndex(-1);
}

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

void AppMenuApplet::trigger(QQuickItem *ctx, int idx)
{
    if (m_currentIndex == idx) {
        return;
    }

    if (m_windowMenu && m_windowMenu->isVisible()) {
        m_windowMenu->hide();
    }
    if (m_systemMenu && m_systemMenu->isVisible()) {
        m_systemMenu->hide();
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen()) {
        return;
    }

    QMenu *actionMenu = createMenu(idx);
    if (actionMenu) {
        auto ungrabMouseHack = [ctx]() {
            if (ctx && ctx->window() && ctx->window()->mouseGrabberItem()) {
                ctx->window()->mouseGrabberItem()->ungrabMouse();
            }
        };

        if (view() == FullView) {
            if (!m_currentMenu) {
                m_currentMenu = new QMenu(qobject_cast<QWidget *>(actionMenu->parent()));
                connect(m_currentMenu, &QMenu::aboutToHide, this, &AppMenuApplet::onMenuAboutToHide, Qt::UniqueConnection);
            } else if (m_sourceMenu != actionMenu) {
                auto menuAction = m_currentMenu->menuAction();
                for (QAction *action : m_currentMenu->actions()) {
                    m_currentMenu->removeAction(action);
                    m_sourceMenu->addAction(action);
                }
                menuAction->setMenu(m_sourceMenu);
            }
            m_sourceMenu = actionMenu;
            auto menuAction = m_sourceMenu->menuAction();
            for (QAction *action : m_sourceMenu->actions()) {
                m_sourceMenu->removeAction(action);
                m_currentMenu->addAction(action);
            }
            menuAction->setMenu(m_currentMenu);
        } else {
            m_currentMenu = actionMenu;
            m_sourceMenu = actionMenu;
        }

        QTimer::singleShot(0, ctx, ungrabMouseHack);

        const auto &geo = ctx->window()->screen()->availableVirtualGeometry();
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
            m_currentMenu->popup(pos);
            connect(actionMenu, &QMenu::aboutToHide, this, &AppMenuApplet::onMenuAboutToHide, Qt::UniqueConnection);
        }

        setCurrentIndex(idx);

    } else {
        if (auto *action = m_model->index(idx, 0).data(AppMenuModel::ActionRole).value<QAction *>()) {
            Q_ASSERT(!action->menu());
            action->trigger();
        }
    }
}

void AppMenuApplet::triggerWindowMenu(QQuickItem *ctx)
{
    static constexpr int WINDOW_MENU_INDEX = -2;

    if (m_currentIndex == WINDOW_MENU_INDEX) {
        return;
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen()) {
        return;
    }

    if (m_currentMenu && m_currentMenu->isVisible()) {
        m_currentMenu->hide();
    }
    if (m_systemMenu && m_systemMenu->isVisible()) {
        m_systemMenu->hide();
    }

    auto *appModel = qobject_cast<AppMenuModel *>(m_model.data());
    if (!appModel) {
        return;
    }

    auto *tasks = appModel->tasksModel();
    const QModelIndex activeTask = tasks->activeTask();
    if (!activeTask.isValid()) {
        return;
    }

    if (!m_windowMenu) {
        m_windowMenu = std::make_unique<QMenu>();
        connect(m_windowMenu.get(), &QMenu::aboutToHide, this, &AppMenuApplet::onWindowMenuAboutToHide);
        m_windowMenu->installEventFilter(this);
    }
    m_windowMenu->clear();

    const bool isClosable = tasks->data(activeTask, TaskManager::AbstractTasksModel::IsClosable).toBool();
    const bool isMinimizable = tasks->data(activeTask, TaskManager::AbstractTasksModel::IsMinimizable).toBool();
    const bool isMaximizable = tasks->data(activeTask, TaskManager::AbstractTasksModel::IsMaximizable).toBool();
    const bool isMaximized = tasks->data(activeTask, TaskManager::AbstractTasksModel::IsMaximized).toBool();
    const bool isFullScreenable = tasks->data(activeTask, TaskManager::AbstractTasksModel::IsFullScreenable).toBool();
    const bool isFullScreen = tasks->data(activeTask, TaskManager::AbstractTasksModel::IsFullScreen).toBool();

    auto *closeAction = m_windowMenu->addAction(
        QIcon::fromTheme(QStringLiteral("window-close")),
        QStringLiteral("Close"));
    closeAction->setEnabled(isClosable);
    connect(closeAction, &QAction::triggered, tasks, [tasks, activeTask]() {
        tasks->requestClose(activeTask);
    });

    m_windowMenu->addSeparator();

    auto *minimizeAction = m_windowMenu->addAction(
        QIcon::fromTheme(QStringLiteral("window-minimize")),
        QStringLiteral("Minimize"));
    minimizeAction->setEnabled(isMinimizable);
    connect(minimizeAction, &QAction::triggered, tasks, [tasks, activeTask]() {
        tasks->requestToggleMinimized(activeTask);
    });

    auto *zoomAction = m_windowMenu->addAction(
        QIcon::fromTheme(isMaximized ? QStringLiteral("window-restore") : QStringLiteral("window-maximize")),
        isMaximized ? QStringLiteral("Restore") : QStringLiteral("Zoom"));
    zoomAction->setEnabled(isMaximizable);
    connect(zoomAction, &QAction::triggered, tasks, [tasks, activeTask]() {
        tasks->requestToggleMaximized(activeTask);
    });

    m_windowMenu->addSeparator();

    auto *fullScreenAction = m_windowMenu->addAction(
        QIcon::fromTheme(QStringLiteral("view-fullscreen")),
        isFullScreen ? QStringLiteral("Exit Full Screen") : QStringLiteral("Enter Full Screen"));
    fullScreenAction->setEnabled(isFullScreenable);
    connect(fullScreenAction, &QAction::triggered, tasks, [tasks, activeTask]() {
        tasks->requestToggleFullScreen(activeTask);
    });

    auto ungrabMouseHack = [ctx]() {
        if (ctx && ctx->window() && ctx->window()->mouseGrabberItem()) {
            ctx->window()->mouseGrabberItem()->ungrabMouse();
        }
    };

    QTimer::singleShot(0, ctx, ungrabMouseHack);

    const auto &geo = ctx->window()->screen()->availableVirtualGeometry();
    QPoint pos = ctx->window()->mapToGlobal(ctx->mapToScene(QPointF()).toPoint());

    const Qt::Edges edges = edgeFromLocation(location());
    m_windowMenu->setProperty("_breeze_menu_seamless_edges", QVariant::fromValue(edges));

    if (location() == Plasma::Types::TopEdge) {
        pos.setY(pos.y() + ctx->height());
    }

    m_windowMenu->adjustSize();
    pos = QPoint(qBound(geo.x(), pos.x(), geo.x() + geo.width() - m_windowMenu->width()),
                 qBound(geo.y(), pos.y(), geo.y() + geo.height() - m_windowMenu->height()));

    if (!m_windowMenu->isVisible()) {
        m_windowMenu->winId();
        m_windowMenu->windowHandle()->setTransientParent(ctx->window());
        m_windowMenu->popup(pos);
    }

    setCurrentIndex(WINDOW_MENU_INDEX);
}

void AppMenuApplet::onWindowMenuAboutToHide()
{
    setCurrentIndex(-1);
}

static void runCommand(const QString &cmd)
{
    QProcess::startDetached(QStringLiteral("/bin/sh"), {QStringLiteral("-c"), cmd});
}

void AppMenuApplet::triggerSystemMenu(QQuickItem *ctx)
{
    static constexpr int SYSTEM_MENU_INDEX = -3;

    if (m_currentIndex == SYSTEM_MENU_INDEX) {
        return;
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen()) {
        return;
    }

    if (m_currentMenu && m_currentMenu->isVisible()) {
        m_currentMenu->hide();
    }
    if (m_windowMenu && m_windowMenu->isVisible()) {
        m_windowMenu->hide();
    }

    auto *menu = new QMenu;
    menu->setAttribute(Qt::WA_DeleteOnClose);
    m_systemMenu = menu;
    connect(menu, &QMenu::aboutToHide, this, &AppMenuApplet::onSystemMenuAboutToHide);
    menu->installEventFilter(this);

    const auto cfg = config();

    auto icon = [&cfg](const char *key, const QString &fallback) {
        return QIcon::fromTheme(cfg.readEntry(key, fallback));
    };

    menu->addAction(icon("iconAbout", QStringLiteral("computer")),
        QStringLiteral("About This Computer"), this, [this]() {
        Q_EMIT aboutRequested();
    });

    menu->addSeparator();

    menu->addAction(icon("iconSystemSettings", QStringLiteral("preferences-system")),
        QStringLiteral("System Settings\u2026"), []() {
        runCommand(QStringLiteral("systemsettings"));
    });
    menu->addAction(icon("iconAppStore", QStringLiteral("software-store-symbolic")),
        QStringLiteral("App Store\u2026"), []() {
        runCommand(QStringLiteral("plasma-discover"));
    });

    menu->addSeparator();

    menu->addAction(icon("iconForceQuit", QStringLiteral("dialog-cancel")),
        QStringLiteral("Force Quit\u2026"), []() {
        runCommand(QStringLiteral("qdbus6 org.kde.KWin /KWin slotKillWindow || xkill"));
    });

    menu->addSeparator();

    menu->addAction(icon("iconSleep", QStringLiteral("system-suspend")),
        QStringLiteral("Sleep"), [cmd = cfg.readEntry("cmdSleep",
        QStringLiteral("qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement requestSuspend || systemctl suspend"))]() {
        runCommand(cmd);
    });
    menu->addAction(icon("iconRestart", QStringLiteral("system-reboot")),
        QStringLiteral("Restart\u2026"), [cmd = cfg.readEntry("cmdRestart",
        QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptReboot"))]() {
        runCommand(cmd);
    });
    menu->addAction(icon("iconShutDown", QStringLiteral("system-shutdown")),
        QStringLiteral("Shut Down\u2026"), [cmd = cfg.readEntry("cmdShutDown",
        QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"))]() {
        runCommand(cmd);
    });

    menu->addSeparator();

    menu->addAction(icon("iconLockScreen", QStringLiteral("system-lock-screen")),
        QStringLiteral("Lock Screen"), [cmd = cfg.readEntry("cmdLockScreen",
        QStringLiteral("qdbus6 org.freedesktop.ScreenSaver /ScreenSaver Lock || loginctl lock-session"))]() {
        runCommand(cmd);
    });
    const QString firstName = KUser().property(KUser::FullName).toString().section(QLatin1Char(' '), 0, 0);
    menu->addAction(icon("iconLogOut", QStringLiteral("user-identity")),
        QStringLiteral("Log Out %1\u2026").arg(firstName), [cmd = cfg.readEntry("cmdLogOut",
        QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptLogout"))]() {
        runCommand(cmd);
    });

    auto ungrabMouseHack = [ctx]() {
        if (ctx && ctx->window() && ctx->window()->mouseGrabberItem()) {
            ctx->window()->mouseGrabberItem()->ungrabMouse();
        }
    };

    QTimer::singleShot(0, ctx, ungrabMouseHack);

    const auto &geo = ctx->window()->screen()->availableVirtualGeometry();
    QPoint pos = ctx->window()->mapToGlobal(ctx->mapToScene(QPointF()).toPoint());

    const Qt::Edges edges = edgeFromLocation(location());
    menu->setProperty("_breeze_menu_seamless_edges", QVariant::fromValue(edges));

    if (location() == Plasma::Types::TopEdge) {
        pos.setY(pos.y() + ctx->height());
    }

    menu->setMinimumWidth(menu->sizeHint().width() + 55);
    menu->adjustSize();
    pos = QPoint(qBound(geo.x(), pos.x(), geo.x() + geo.width() - menu->width()),
                 qBound(geo.y(), pos.y(), geo.y() + geo.height() - menu->height()));

    menu->winId();
    menu->windowHandle()->setTransientParent(ctx->window());
    menu->popup(pos);

    setCurrentIndex(SYSTEM_MENU_INDEX);
}

void AppMenuApplet::onSystemMenuAboutToHide()
{
    setCurrentIndex(-1);
}

bool AppMenuApplet::eventFilter(QObject *watched, QEvent *event)
{
    auto *menu = qobject_cast<QMenu *>(watched);
    if (!menu) {
        return false;
    }

    if (event->type() == QEvent::KeyPress) {
        auto *e = static_cast<QKeyEvent *>(event);

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
        auto *e = static_cast<QMouseEvent *>(event);

        if (!m_buttonGrid || !m_buttonGrid->window()) {
            return false;
        }

        const QPointF &windowLocalPos = m_buttonGrid->window()->mapFromGlobal(e->globalPosition());
        const QPointF &buttonGridLocalPos = m_buttonGrid->mapFromScene(windowLocalPos);
        auto *item = m_buttonGrid->childAt(buttonGridLocalPos.x(), buttonGridLocalPos.y());
        if (!item) {
            return false;
        }

        bool ok;
        const int buttonIndex = item->property("buttonIndex").toInt(&ok);
        if (!ok) {
            return false;
        }

        Q_EMIT requestActivateIndex(buttonIndex);
    }

    return false;
}

K_PLUGIN_CLASS_WITH_JSON(AppMenuApplet, "metadata.json")

#include "appmenuapplet.moc"
#include "moc_appmenuapplet.cpp"
