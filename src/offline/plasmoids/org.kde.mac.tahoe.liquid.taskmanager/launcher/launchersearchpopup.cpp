// SPDX-License-Identifier: GPL-3.0-or-later
#include "launchersearchpopup.h"
#include "glasssettings.h"

#include <Plasma/Theme>
#include <PlasmaQuick/PlasmaShellWaylandIntegration>
#include <KWindowSystem>
#include <KX11Extras>
#include <QEvent>
#include <QGuiApplication>
#include <QScreen>
#include <QStandardPaths>
#include <algorithm>

LauncherSearchPopup::LauncherSearchPopup()
    : PlasmaQuick::PopupPlasmaWindow(QStandardPaths::locate(QStandardPaths::GenericDataLocation,
                                       QStringLiteral("plasma/desktoptheme/") + Plasma::Theme().themeName()
                                       + QStringLiteral("/dialogs/launcher-search.svgz")).isEmpty()
                                       ? QStringLiteral("dialogs/background")
                                       : QStringLiteral("dialogs/launcher-search"))
{
    setTitle(QStringLiteral("mttkde-search"));
    auto *glassSettings = new GlassSettings(this);
    glassSettings->setComponent(QStringLiteral("search"));
    glassSettings->setWindow(this);
    setFlags(flags() | Qt::Dialog);
    // Match Plasma's applet role so window effects preserve the SVG capsule.
    if (KWindowSystem::isPlatformX11()) {
        KX11Extras::setType(winId(), NET::AppletPopup);
    } else if (KWindowSystem::isPlatformWayland()) {
        PlasmaShellWaylandIntegration::get(this)->setRole(QtWayland::org_kde_plasma_surface::role_appletpopup);
    }
    connect(qGuiApp, &QGuiApplication::focusWindowChanged, this, &LauncherSearchPopup::focusWindowChanged);
    connect(this, &PlasmaQuick::PopupPlasmaWindow::visualParentChanged, this, [this] {
        for (const auto &connection : m_anchorGeometryConnections) {
            disconnect(connection);
        }
        m_anchorGeometryConnections.clear();
        auto *anchor = visualParent();
        if (!anchor) {
            return;
        }
        // Item layout can settle after the native popup/window configure.
        // Plasma tracks the parent window position, not this item geometry.
        const auto reposition = [this] {
            queuePositionUpdate();
            requestUpdate();
        };
        m_anchorGeometryConnections = {
            connect(anchor, &QQuickItem::xChanged, this, reposition),
            connect(anchor, &QQuickItem::yChanged, this, reposition),
            connect(anchor, &QQuickItem::widthChanged, this, reposition),
            connect(anchor, &QQuickItem::heightChanged, this, reposition),
        };
        reposition();
    });
    connect(this, &QWindow::transientParentChanged, this, [this](QWindow *parent) {
        if (m_anchorWindow) {
            m_anchorWindow->removeEventFilter(this);
        }
        m_anchorWindow = parent;
        if (parent) {
            parent->installEventFilter(this);
        }
    });
}

QWindow *LauncherSearchPopup::focusWindow() const
{
    return QGuiApplication::focusWindow();
}

bool LauncherSearchPopup::eventFilter(QObject *watched, QEvent *event)
{
    if (watched == m_anchorWindow && isVisible()
        && (event->type() == QEvent::Move || event->type() == QEvent::Resize)) {
        queuePositionUpdate();
        requestUpdate();
    }
    return PlasmaQuick::PopupPlasmaWindow::eventFilter(watched, event);
}

bool LauncherSearchPopup::event(QEvent *event)
{
    const bool handled = PlasmaQuick::PopupPlasmaWindow::event(event);
    // A reopened Wayland parent can still report its previous QScreen until
    // wl_surface.enter arrives. Plasma's constraint calculation then clamps
    // this capsule onto the old monitor. Resolve the output from the anchor's
    // global coordinates on both backends, including before that notification.
    if (isVisible()
        && (event->type() == QEvent::Show || event->type() == QEvent::Resize
            || event->type() == QEvent::UpdateRequest)) {
        const auto anchor = visualParent();
        if (anchor && anchor->window() && anchor->window()->screen()) {
            const QPointF topLeft = anchor->mapToGlobal(QPointF(0, 0));
            auto *targetScreen = QGuiApplication::screenAt(
                anchor->mapToGlobal(QPointF(anchor->width() / 2, anchor->height() / 2)).toPoint());
            if (!targetScreen) {
                targetScreen = anchor->window()->screen();
            }
            const QRect available = targetScreen->availableGeometry();
            const int left = qRound(topLeft.x() + (anchor->width() - width()) / 2);
            const int top = qRound(topLeft.y()) - height() - margin();
            const QPoint position(std::clamp(left, available.left(),
                                   std::max(available.left(), available.right() + 1 - width())),
                        std::clamp(top, available.top(),
                                   std::max(available.top(), available.bottom() + 1 - height())));
            setPosition(position);
            if (KWindowSystem::isPlatformWayland()) {
                PlasmaShellWaylandIntegration::get(this)->setPosition(position);
            }
        }
    }
    return handled;
}
