/*
  SPDX-FileCopyrightText: 2024 David Edmundson <davidedmundson@kde.org>
  SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#include "notificationbanner.h"

#include <KWindowSystem>
#include <KX11Extras>
#include <PlasmaQuick/PlasmaShellWaylandIntegration>

NotificationBanner::NotificationBanner()
    : QQuickWindow()
{
    setColor(Qt::transparent);
    setFlags(Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint | Qt::WindowDoesNotAcceptFocus);
    PlasmaShellWaylandIntegration::get(this)->setRole(QtWayland::org_kde_plasma_surface::role_notification);
    PlasmaShellWaylandIntegration::get(this)->setTakesFocus(false);

    if (KWindowSystem::isPlatformX11()) {
        KX11Extras::setOnAllDesktops(winId(), true);
        KX11Extras::setType(winId(), NET::Notification);
    }
}

NotificationBanner::~NotificationBanner() = default;

QQuickItem *NotificationBanner::mainItem() const
{
    return m_mainItem;
}

void NotificationBanner::setMainItem(QQuickItem *item)
{
    if (m_mainItem == item) {
        return;
    }
    if (m_mainItem) {
        m_mainItem->setParentItem(nullptr);
    }
    m_mainItem = item;
    if (item) {
        item->setParentItem(contentItem());
    }
    Q_EMIT mainItemChanged();
}

bool NotificationBanner::takeFocus() const
{
    return m_takeFocus;
}

void NotificationBanner::setTakeFocus(bool takeFocus)
{
    if (m_takeFocus == takeFocus) {
        return;
    }
    PlasmaShellWaylandIntegration::get(this)->setTakesFocus(takeFocus);
    QWindow::setFlag(Qt::WindowDoesNotAcceptFocus, !takeFocus);

    m_takeFocus = takeFocus;
    Q_EMIT takeFocusChanged();
}

bool NotificationBanner::isCritical() const
{
    return m_critical;
}

void NotificationBanner::setIsCritical(bool critical)
{
    if (m_critical == critical) {
        return;
    }

    m_critical = critical;

    auto role = critical ? QtWayland::org_kde_plasma_surface::role_criticalnotification : QtWayland::org_kde_plasma_surface::role_notification;
    PlasmaShellWaylandIntegration::get(this)->setRole(role);

    if (KWindowSystem::isPlatformX11()) {
        KX11Extras::setType(winId(), critical ? NET::CriticalNotification : NET::Notification);
    }

    Q_EMIT isCriticalChanged();
}

bool NotificationBanner::event(QEvent *e)
{
    // moveEvents only occur when we have a platform window, so we need to explicitly sync on creation
    if (e->type() == QEvent::PlatformSurface) {
        auto ps = static_cast<QPlatformSurfaceEvent *>(e);
        if (ps->surfaceEventType() == QPlatformSurfaceEvent::SurfaceCreated) {
            PlasmaShellWaylandIntegration::get(this)->setPosition(QPoint(x(), y()));
        }
    }
    return QQuickWindow::event(e);
}

void NotificationBanner::moveEvent(QMoveEvent *me)
{
    PlasmaShellWaylandIntegration::get(this)->setPosition(me->pos());
    QQuickWindow::moveEvent(me);
    update();
}

#include "moc_notificationbanner.cpp"
