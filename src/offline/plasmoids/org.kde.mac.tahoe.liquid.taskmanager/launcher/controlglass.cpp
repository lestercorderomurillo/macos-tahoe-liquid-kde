// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include "contrastpreset.h"
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
    connect(&m_frame, &MaterialSample::changed, this, &PopupBackdrop::notifyBackdropChanged);
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("inkPixels"), this, SLOT(pixelReply(int,QRect,QString,QByteArray)));
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("controlBackdrop"), this, SLOT(updateBackdrop(int,QRect,QRect,QByteArray,QString)));
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("movingControlSample"), this, SLOT(movingControlSample(int,QRect,QString)));
}

void PopupBackdrop::pixelReply(int pid, const QRect &frame, const QString &role, const QByteArray &data)
{
    if (m_pixels.receive(pid, frame, role, data)) notifyBackdropChanged();
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
    if (title == QStringLiteral("mttkde-notifications")) {
        const int tolerance = BackdropGeometry::edgeTolerance(*m_window);
        if (qAbs(frame.x() - m_window->x()) > tolerance || qAbs(frame.y() - m_window->y()) > tolerance) return;
    }
    if (dragging && !m_lastFrame.isEmpty() && frame.topLeft() != m_lastFrame.topLeft()) m_ink.moved();
    if (!dragging) m_ink.stationary();
    m_pixels.locate(frame, title);
    m_lastFrame = frame;
    if (title == QStringLiteral("mttkde-apps") || title == QStringLiteral("mttkde-search"))
        m_frame.findWindowFrame(qobject_cast<QQuickWindow *>(m_window.data()), QStringLiteral("dialogs/background"));
    m_sampleBounds = bounds.translated(-frame.topLeft());
    m_gridSide = colors.size() == 64 * 64 * 3 ? 64 : 8;
    m_backdropGrid = colors;
    notifyBackdropChanged();
}

void PopupBackdrop::notifyBackdropChanged()
{
    ++m_revision;
    Q_EMIT backdropChanged();
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
    }).tone(base);
}

QColor PopupBackdrop::animatedForegroundAt(QObject *item, QPointF point, QSizeF radius, QColor base, QColor fill)
{
    return m_ink.color(item, base, foregroundAt(point, radius, base, fill));
}

QColor PopupBackdrop::frameFillAt(QPointF point, QColor fallback) const
{
    const auto painted = m_frame.at(point);
    return painted.isValid() ? painted : fallback;
}

QColor PopupBackdrop::surfaceForeground(QObject *item, QRectF bounds, QColor reference, QColor base, QColor fill, const QJsonObject &profile, MaterialSample *material, QColor overlay, int run)
{
    if (m_backdropGrid.isEmpty() || bounds.isEmpty()) return base;
    GlassInk::Samples samples;
    const auto count = profile.value(QStringLiteral("sampleCount")).toInt(15);
    const auto *control = qobject_cast<const ControlGlass *>(this);
    const bool wholeControl = control && profile.value(QStringLiteral("scope")).toString() == QStringLiteral("component");
    const auto visibleSurfaces = wholeControl ? control->surfaces() : QVariantList{};
    GlassInk::zonePoints(bounds, count, [&](QPointF p) {
        QColor localFill = fill;
        MaterialSample *layer = material;
        if (!visibleSurfaces.isEmpty()) {
            bool inside = false;
            for (const auto &shape : visibleSurfaces) {
                const auto data = shape.toMap();
                const QRectF rect(data.value(QStringLiteral("x")).toDouble(), data.value(QStringLiteral("y")).toDouble(),
                                  data.value(QStringLiteral("width")).toDouble(), data.value(QStringLiteral("height")).toDouble());
                if (!rect.contains(p) || !data.value(QStringLiteral("fill")).isValid()) continue;
                localFill = data.value(QStringLiteral("fill")).value<QColor>();
                layer = qobject_cast<MaterialSample *>(data.value(QStringLiteral("material")).value<QObject *>());
                inside = true;
                break;
            }
            if (!inside) return;
        }
        const QColor painted = layer ? layer->at(p) : QColor();
        const QColor pixel = profile.value(QStringLiteral("scope")).toString() == QStringLiteral("letter") ? m_pixels.at(p) : QColor();
        const QColor surface = GlassInk::composite(pixel.isValid() ? pixel : backdropAt(p), painted.isValid() ? painted : frameFillAt(p, localFill));
        samples.add(GlassInk::composite(surface, overlay));
    });
    const auto corrected = m_history.tone(samples, reference, ContrastPreset::settings(profile), item, run);
    return m_ink.color(item, base, GlassInk::applyRoleCorrection(base, reference, corrected));
}

QColor PopupBackdrop::animatedLabelForeground(QObject *item, QPointF point, QSizeF radius, QColor base, QColor fill)
{
    QColor target = base;
    if (!m_backdropGrid.isEmpty()) {
        target = GlassInk::sample(GlassInk::label, point, radius, [&](QPointF p) {
            return GlassInk::composite(backdropAt(p), fill);
        }).tone(base);
    }
    return m_ink.color(item, base, target);
}

QList<QColor> PopupBackdrop::categorySamples(QPointF point, QSizeF radius, QRectF viewport, QColor fill, int count, QColor overlay) const
{
    QList<QColor> surfaces;
    if (m_backdropGrid.isEmpty()) return surfaces;
    GlassInk::forEachPoint({std::clamp(count, 1, 256), 1}, point, radius, [&](QPointF p, double) {
        if (p.x() >= viewport.left() && p.x() < viewport.right())
            surfaces.append(GlassInk::composite(GlassInk::composite(backdropAt(p), frameFillAt(p, fill)), overlay));
    });
    return surfaces;
}

QColor PopupBackdrop::groupForeground(QObject *item, QColor base, const QList<QColor> &surfaces)
{
    return profileGroupForeground(item, base, surfaces, {});
}

QColor PopupBackdrop::profileGroupForeground(QObject *item, QColor base, const QList<QColor> &surfaces, const QJsonObject &profile)
{
    if (m_backdropGrid.isEmpty()) return base;
    GlassInk::Samples samples;
    for (const auto &surface : surfaces) samples.add(surface);
    return m_ink.color(item, base, m_history.tone(samples, base, ContrastPreset::settings(profile), item));
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
    m_frame.setSource(nullptr);
    m_window = window;
    m_ink.observe(window);
    const auto clear = [this] {
        m_pixels.locate({}, {});
        m_lastFrame = {};
        m_movingFrame = {};
        m_ink.reset();
        m_backdropGrid.clear();
        notifyBackdropChanged();
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
    notifyBackdropChanged();
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
