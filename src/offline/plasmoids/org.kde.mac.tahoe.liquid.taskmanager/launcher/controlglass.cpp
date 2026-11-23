// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include "glassink.h"
#include "backdropgeometry.h"
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

PopupBackdrop::PopupBackdrop(QObject *parent) : QObject(parent)
{
    connect(this, &PopupBackdrop::appearanceChanged, this, &PopupBackdrop::refreshFamily);
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("controlBackdrop"), this, SLOT(updateBackdrop(int,QRect,QRect,QByteArray,QString)));
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("movingControlSample"), this, SLOT(movingControlSample(int,QRect,QString)));
}

void PopupBackdrop::movingControlSample(int pid, const QRect &frame, const QString &title)
{
    if (m_window && m_window->isVisible() && m_window->title() == title && pid == QCoreApplication::applicationPid())
        m_movingFrame = frame;
}

void PopupBackdrop::updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &colors, const QString &title)
{
    const bool dragging = frame == m_movingFrame && !m_movingFrame.isEmpty();
    m_movingFrame = {};
    if (!m_window || !m_window->isVisible() || m_window->title() != title
        || pid != QCoreApplication::applicationPid() || !BackdropGeometry::sizeMatches(frame, *m_window)
        // Wayland repositions the anchored Plasma dialog relative to its panel.
        || !m_window->screen() || !m_window->screen()->geometry().intersects(frame)
        || bounds.isEmpty() || (colors.size() != 8 * 8 * 3 && colors.size() != 64 * 64 * 3)) return;
    if (dragging && !m_lastFrame.isEmpty() && frame.topLeft() != m_lastFrame.topLeft()) m_ink.moved();
    if (!dragging) m_ink.stationary();
    m_lastFrame = frame;
    m_sampleBounds = bounds.translated(-frame.topLeft());
    m_gridSide = colors.size() == 64 * 64 * 3 ? 64 : 8;
    m_backdropGrid = colors;
    refreshFamily();
}

void PopupBackdrop::refreshFamily()
{
    m_family = m_backdropGrid.isEmpty() ? GlassInk::familyOf(m_preferredInk) : componentSamples().family(m_preferredInk);
    ++m_revision;
    Q_EMIT backdropChanged();
}

void PopupBackdrop::addMaterial(GlassInk::Samples &samples, const QRectF &bounds, QColor fill) const
{
    const QRectF visible = bounds.intersected(m_sampleBounds);
    if (visible.isEmpty()) return;
    const auto &profile = GlassInk::component;
    // Sample the center of each cell. Larger glass islands contribute proportionally
    // more than small ones and transparent space between controls contributes nothing.
    const QSizeF radius(visible.width() * .5 * (1. - 1. / profile.columns),
                        visible.height() * .5 * (1. - 1. / profile.rows));
    GlassInk::forEachPoint(profile, visible.center(), radius, [&](QPointF point, double weight) {
        samples.add(GlassInk::composite(backdropAt(point), fill), weight * visible.width() * visible.height());
    });
}

GlassInk::Samples PopupBackdrop::componentSamples() const
{
    GlassInk::Samples samples;
    addMaterial(samples, m_sampleBounds, m_componentFill);
    return samples;
}

GlassInk::Samples ControlGlass::componentSamples() const
{
    GlassInk::Samples samples;
    bool hasMaterial = false;
    for (const auto &value : m_surfaces) {
        const auto surface = value.toMap();
        const QColor fill = surface.value(QStringLiteral("fill")).value<QColor>();
        if (!fill.isValid() || !surface.value(QStringLiteral("glass"), true).toBool()) continue;
        hasMaterial = true;
        const QRectF bounds(surface.value(QStringLiteral("x")).toDouble(), surface.value(QStringLiteral("y")).toDouble(),
                            surface.value(QStringLiteral("width")).toDouble(), surface.value(QStringLiteral("height")).toDouble());
        addMaterial(samples, bounds, fill);
    }
    return hasMaterial ? samples : PopupBackdrop::componentSamples();
}

QColor PopupBackdrop::backdropAt(QPointF point) const
{
    if (m_backdropGrid.isEmpty()) return Qt::transparent;
    const int x = std::clamp(int((point.x() - m_sampleBounds.x()) * m_gridSide / m_sampleBounds.width()), 0, m_gridSide - 1);
    const int y = std::clamp(int((point.y() - m_sampleBounds.y()) * m_gridSide / m_sampleBounds.height()), 0, m_gridSide - 1);
    const auto *rgb = reinterpret_cast<const unsigned char *>(m_backdropGrid.constData()) + (y * m_gridSide + x) * 3;
    return QColor(rgb[0], rgb[1], rgb[2]);
}

QColor PopupBackdrop::foregroundAt(QPointF point, QSizeF radius, QColor base, QColor fill) const
{
    if (m_backdropGrid.isEmpty()) return base;
    return GlassInk::sample(GlassInk::control, point, radius, [&](QPointF p) {
        return GlassInk::composite(backdropAt(p), fill);
    }).tone(base, m_family);
}

QColor PopupBackdrop::animatedForegroundAt(QObject *item, QPointF point, QSizeF radius, QColor base, QColor fill)
{
    return m_ink.color(item, base, foregroundAt(point, radius, base, fill));
}

QColor PopupBackdrop::animatedLabelForeground(QObject *item, QPointF point, QSizeF radius, QColor base, QColor fill)
{
    QColor target = base;
    if (!m_backdropGrid.isEmpty()) {
        target = GlassInk::sample(GlassInk::label, point, radius, [&](QPointF p) {
            return GlassInk::composite(backdropAt(p), fill);
        }).tone(base, m_family);
    }
    return m_ink.color(item, base, target);
}

QList<QColor> PopupBackdrop::categorySamples(QPointF point, QSizeF radius, QRectF viewport, QColor fill) const
{
    QList<QColor> surfaces;
    if (m_backdropGrid.isEmpty()) return surfaces;
    GlassInk::forEachPoint(GlassInk::categoryRow, point, radius, [&](QPointF p, double) {
        if (p.x() >= viewport.left() && p.x() < viewport.right())
            surfaces.append(GlassInk::composite(backdropAt(p), fill));
    });
    return surfaces;
}

QColor PopupBackdrop::groupForeground(QObject *item, QColor base, const QList<QColor> &surfaces)
{
    if (m_backdropGrid.isEmpty()) return base;
    GlassInk::Samples samples;
    for (const auto &surface : surfaces) samples.add(surface);
    return m_ink.color(item, base, samples.tone(base, m_family));
}

QRegion ControlGlass::regionFor(const QVariantList &surfaces, bool glassOnly)
{
    QRegion result;
    for (const auto &value : surfaces) {
        const auto surface = value.toMap();
        if (glassOnly && surface.contains(QStringLiteral("glass")) && !surface.value(QStringLiteral("glass")).toBool()) {
            continue;
        }
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

void PopupBackdrop::setWindow(QWindow *window)
{
    if (m_window == window) return;
    if (m_window) disconnect(m_window, &QWindow::visibleChanged, this, nullptr);
    m_window = window;
    m_ink.observe(window);
    const auto clear = [this] {
        m_lastFrame = {};
        m_movingFrame = {};
        m_ink.reset();
        m_backdropGrid.clear();
        refreshFamily();
    };
    if (window) connect(window, &QWindow::visibleChanged, this, [clear](bool visible) {
        if (!visible) clear();
    });
    clear();
    Q_EMIT windowChanged();
}

void ControlGlass::setWindow(QWindow *window)
{
    if (m_window == window) return;
    if (m_window) m_window->removeEventFilter(this);
    disconnect(m_frameConnection);
    PopupBackdrop::setWindow(window);
    if (m_window) m_window->installEventFilter(this);
    if (auto quickWindow = qobject_cast<QQuickWindow *>(m_window.data())) {
        // Plasma Dialog::NoBackground clears blur and the input mask during
        // layout/theme/expose updates, after Show's queued callback. Restore
        // our islands on the GUI thread immediately before scene preparation.
        // No polling or extra frame request: KWindowEffects caches the region.
        m_frameConnection = connect(quickWindow, &QQuickWindow::afterAnimating,
                                    this, &ControlGlass::apply);
    }
    apply();
}

void ControlGlass::setSurfaces(const QVariantList &surfaces)
{
    if (m_surfaces == surfaces) return;
    m_surfaces = surfaces;
    m_region = regionFor(surfaces);
    m_inputRegion = regionFor(surfaces, false);
    refreshFamily();
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
    const QRegion inputRegion = m_maskWindow ? m_inputRegion : QRegion();
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
