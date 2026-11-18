/*
  SPDX-FileCopyrightText: 2024 David Edmundson <davidedmundson@kde.org>
  SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#include "notificationbanner.h"

#include <KWindowSystem>
#include <QDBusConnection>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QGuiApplication>
#include <cmath>
#include <KX11Extras>
#include <PlasmaQuick/PlasmaShellWaylandIntegration>

NotificationBanner::NotificationBanner()
    : QQuickWindow()
{
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("backdropSample"), this, SLOT(updateBackdrop(QString)));
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

void NotificationBanner::updateBackdrop(const QString &sample)
{
    if (!isVisible()) return;
    const auto object = QJsonDocument::fromJson(sample.toUtf8()).object();
    if (object.value(QStringLiteral("pid")).toInteger() != qGuiApp->applicationPid()) return;
    const QRect bounds(object.value(QStringLiteral("x")).toInt(), object.value(QStringLiteral("y")).toInt(),
                       object.value(QStringLiteral("width")).toInt(), object.value(QStringLiteral("height")).toInt());
    if (bounds != geometry()) return;
    const auto rgb = object.value(QStringLiteral("rgb")).toArray();
    if (rgb.size() != 3) return;
    for (const auto &value : rgb) {
        if (!value.isDouble() || !std::isfinite(value.toDouble()) || value.toDouble() < 0 || value.toDouble() > 1) return;
    }
    const QColor color = QColor::fromRgbF(rgb.at(0).toDouble(), rgb.at(1).toDouble(), rgb.at(2).toDouble());
    if (color == m_backdropColor) return;
    m_backdropColor = color;
    Q_EMIT backdropColorChanged();
}

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
