/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "menuapplet.h"

#include <QMenu>
#include <QProcess>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>

MenuApplet::MenuApplet(QObject *parent, const KPluginMetaData &data, const QVariantList &args)
    : Plasma::Applet(parent, data, args)
{
}

MenuApplet::~MenuApplet() = default;

static Qt::Edges edgeFromLocation(Plasma::Types::Location location)
{
    switch (location) {
    case Plasma::Types::TopEdge:    return Qt::TopEdge;
    case Plasma::Types::BottomEdge: return Qt::BottomEdge;
    case Plasma::Types::LeftEdge:   return Qt::LeftEdge;
    case Plasma::Types::RightEdge:  return Qt::RightEdge;
    default: break;
    }
    return {};
}

static void runCommand(const QString &cmd)
{
    QProcess::startDetached(QStringLiteral("/bin/sh"), {QStringLiteral("-c"), cmd});
}

void MenuApplet::trigger(QQuickItem *ctx)
{
    // Toggle: if menu is already visible, close it
    if (m_currentMenu) {
        m_currentMenu->close();
        return;
    }

    if (!ctx || !ctx->window() || !ctx->window()->screen())
        return;

    auto *menu = new QMenu;
    menu->setAttribute(Qt::WA_DeleteOnClose);
    m_currentMenu = menu;

    connect(menu, &QMenu::aboutToHide, this, [this]() {
        m_currentMenu = nullptr;
    });

    // ── build the menu ──────────────────────────────────────────────
    menu->addAction(QStringLiteral("About This Computer"), this, [this]() {
        Q_EMIT aboutRequested();
    });

    menu->addSeparator();

    menu->addAction(QStringLiteral("System Settings\u2026"), []() {
        runCommand(QStringLiteral("systemsettings"));
    });
    menu->addAction(QStringLiteral("App Store\u2026"), []() {
        runCommand(QStringLiteral("plasma-discover"));
    });

    menu->addSeparator();

    menu->addAction(QStringLiteral("Force Quit\u2026"), []() {
        runCommand(QStringLiteral("qdbus6 org.kde.KWin /KWin slotKillWindow || xkill"));
    });

    menu->addSeparator();

    const auto cfg = config();
    menu->addAction(QStringLiteral("Sleep"), [cmd = cfg.readEntry("cmdSleep",
        QStringLiteral("qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement requestSuspend || systemctl suspend"))]() {
        runCommand(cmd);
    });
    menu->addAction(QStringLiteral("Restart\u2026"), [cmd = cfg.readEntry("cmdRestart",
        QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptReboot"))]() {
        runCommand(cmd);
    });
    menu->addAction(QStringLiteral("Shut Down\u2026"), [cmd = cfg.readEntry("cmdShutDown",
        QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"))]() {
        runCommand(cmd);
    });

    menu->addSeparator();

    menu->addAction(QStringLiteral("Lock Screen"), [cmd = cfg.readEntry("cmdLockScreen",
        QStringLiteral("qdbus6 org.freedesktop.ScreenSaver /ScreenSaver Lock || loginctl lock-session"))]() {
        runCommand(cmd);
    });
    menu->addAction(QStringLiteral("Log Out\u2026"), [cmd = cfg.readEntry("cmdLogOut",
        QStringLiteral("qdbus6 org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptLogout"))]() {
        runCommand(cmd);
    });

    // ── position & show ─────────────────────────────────────────────
    // Ungrab mouse so the QMenu can receive events
    QTimer::singleShot(0, ctx, [ctx]() {
        if (ctx && ctx->window() && ctx->window()->mouseGrabberItem())
            ctx->window()->mouseGrabberItem()->ungrabMouse();
    });

    const auto &geo = ctx->window()->screen()->availableVirtualGeometry();
    QPoint pos = ctx->window()->mapToGlobal(ctx->mapToScene(QPointF()).toPoint());

    // Seamless edge rendering (Breeze-specific)
    menu->setProperty("_breeze_menu_seamless_edges", QVariant::fromValue(edgeFromLocation(location())));

    if (location() == Plasma::Types::TopEdge)
        pos.setY(pos.y() + static_cast<int>(ctx->height()));

    menu->adjustSize();
    pos = QPoint(qBound(geo.x(), pos.x(), geo.x() + geo.width() - menu->width()),
                 qBound(geo.y(), pos.y(), geo.y() + geo.height() - menu->height()));

    menu->winId();
    menu->windowHandle()->setTransientParent(ctx->window());
    menu->popup(pos);
}

K_PLUGIN_CLASS_WITH_JSON(MenuApplet, "metadata.json")

#include "menuapplet.moc"
#include "moc_menuapplet.cpp"
