// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include <KWindowEffects>
#include <QEvent>
#include <QPainterPath>
#include <QTimer>
#include <algorithm>
#include <cmath>

QRegion ControlGlass::regionFor(const QVariantList &surfaces)
{
    QRegion result;
    for (const auto &value : surfaces) {
        const auto surface = value.toMap();
        const QRectF rect(surface.value(QStringLiteral("x")).toReal(), surface.value(QStringLiteral("y")).toReal(),
                          surface.value(QStringLiteral("width")).toReal(), surface.value(QStringLiteral("height")).toReal());
        const qreal radius = surface.value(QStringLiteral("radius")).toReal();
        if (!std::isfinite(rect.x()) || !std::isfinite(rect.y())
            || !std::isfinite(rect.width()) || !std::isfinite(rect.height())
            || !std::isfinite(radius) || rect.isEmpty()) {
            continue;
        }
        QPainterPath path;
        const qreal bounded = std::clamp(radius, qreal(0), std::min(rect.width(), rect.height()) / 2);
        path.addRoundedRect(rect, bounded, bounded);
        result |= QRegion(path.toFillPolygon().toPolygon());
    }
    return result;
}

void ControlGlass::setWindow(QWindow *window)
{
    if (m_window == window) return;
    if (m_window) m_window->removeEventFilter(this);
    m_window = window;
    if (m_window) m_window->installEventFilter(this);
    Q_EMIT windowChanged();
    apply();
}

void ControlGlass::setSurfaces(const QVariantList &surfaces)
{
    if (m_surfaces == surfaces) return;
    m_surfaces = surfaces;
    Q_EMIT surfacesChanged();
    apply();
}

void ControlGlass::apply()
{
    if (!m_window) return;
    const auto region = regionFor(m_surfaces);
    m_window->setMask(region);
    KWindowEffects::enableBlurBehind(m_window, !region.isEmpty(), region);
}

bool ControlGlass::eventFilter(QObject *object, QEvent *event)
{
    if (object == m_window && (event->type() == QEvent::Show || event->type() == QEvent::PlatformSurface)) {
        // Plasma initializes its native surface during this event. Apply our
        // explicit region afterwards so it cannot become a whole-window blur.
        QTimer::singleShot(0, this, &ControlGlass::apply);
    }
    return QObject::eventFilter(object, event);
}
