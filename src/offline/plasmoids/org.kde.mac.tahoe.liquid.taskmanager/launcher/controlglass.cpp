// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include <KWindowEffects>
#include <QEvent>
#include <QDBusConnection>
#include <QCoreApplication>
#include <QPainterPath>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>
#include <algorithm>
#include <cmath>

ControlGlass::ControlGlass(QObject *parent) : QObject(parent)
{
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("controlBackdrop"), this, SLOT(updateBackdrop(int,QRect,QRect,QByteArray,QString)));
}

void ControlGlass::updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &colors, const QString &title)
{
    if (!m_window || !m_window->isVisible() || m_window->title() != title
        || pid != QCoreApplication::applicationPid() || frame.size() != m_window->size()
        // Wayland repositions the anchored Plasma dialog relative to its panel.
        || !m_window->screen() || !m_window->screen()->geometry().intersects(frame)
        || bounds.isEmpty() || colors.size() != 8 * 8 * 3) return;
    m_sampleBounds = bounds.translated(-frame.topLeft());
    m_backdropGrid = colors;
    ++m_revision;
    Q_EMIT backdropChanged();
}

QColor ControlGlass::backdropAt(QPointF point) const
{
    if (m_backdropGrid.isEmpty()) return Qt::transparent;
    const int x = std::clamp(int((point.x() - m_sampleBounds.x()) * 8 / m_sampleBounds.width()), 0, 7);
    const int y = std::clamp(int((point.y() - m_sampleBounds.y()) * 8 / m_sampleBounds.height()), 0, 7);
    const auto *rgb = reinterpret_cast<const unsigned char *>(m_backdropGrid.constData()) + (y * 8 + x) * 3;
    return QColor(rgb[0], rgb[1], rgb[2]);
}

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
    disconnect(m_frameConnection);
    m_window = window;
    if (m_window) m_window->installEventFilter(this);
    if (auto quickWindow = qobject_cast<QQuickWindow *>(m_window.data())) {
        // Plasma Dialog::NoBackground clears blur and the input mask during
        // layout/theme/expose updates, after Show's queued callback. Restore
        // our islands on the GUI thread immediately before scene preparation.
        // No polling or extra frame request: KWindowEffects caches the region.
        m_frameConnection = connect(quickWindow, &QQuickWindow::afterAnimating,
                                    this, &ControlGlass::apply);
    }
    Q_EMIT windowChanged();
    apply();
}

void ControlGlass::setSurfaces(const QVariantList &surfaces)
{
    if (m_surfaces == surfaces) return;
    m_surfaces = surfaces;
    m_region = regionFor(surfaces);
    Q_EMIT surfacesChanged();
    apply();
}

void ControlGlass::setMaskWindow(bool enabled)
{
    if (m_maskWindow == enabled) return;
    m_maskWindow = enabled;
    Q_EMIT maskWindowChanged();
    apply();
}

void ControlGlass::apply()
{
    if (!m_window) return;
    // Floating notification headers need pointer input and text outside the
    // glass cards. Their blur islands remain independently constrained.
    const QRegion inputRegion = m_maskWindow ? m_region : QRegion();
    if (m_window->mask() != inputRegion) m_window->setMask(inputRegion);
    KWindowEffects::enableBlurBehind(m_window, !m_region.isEmpty(), m_region);
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
