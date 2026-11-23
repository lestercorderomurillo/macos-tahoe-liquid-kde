// SPDX-License-Identifier: GPL-2.0-or-later
#include "shellmenu.h"
#include "../org.kde.mac.tahoe.liquid.taskmanager/launcher/backdropgeometry.h"
#include <KConfigGroup>
#include <KSharedConfig>
#include <QApplication>
#include <QDBusConnection>
#include <QPainter>
#include <QWindow>
#include <algorithm>
#include <cmath>

namespace {
// Preserve the highlight hue while giving selected text enough contrast.
QColor selectionFill(QColor surface, GlassInk::Family family)
{
    const bool lightInk = family == GlassInk::Family::Light;
    const auto readable = [&](QColor fill) {
        return GlassInk::contrastRatio(lightInk ? 1. : 0., GlassInk::luminance(fill)) >= 4.5;
    };
    if (readable(surface)) return surface;
    QColor overlay = lightInk ? Qt::black : Qt::white;
    double lo = 0., hi = 1.;
    for (int i = 0; i < 8; ++i) {
        const double blend = (lo + hi) / 2;
        overlay.setAlphaF(blend);
        if (readable(GlassInk::composite(surface, overlay))) hi = blend;
        else lo = blend;
    }
    overlay.setAlphaF(hi);
    return GlassInk::composite(surface, overlay);
}
}

ShellMenu::ShellMenu(QWidget *parent) : QMenu(parent)
{
    setProperty("_mttkde_shell_menu", true);
    connect(this, &QMenu::aboutToShow, this, &ShellMenu::reloadTinting);
    QDBusConnection::sessionBus().connect(QString(), QStringLiteral("/org/kde/MacTahoe/Glass"),
        QStringLiteral("org.kde.MacTahoe.Glass"), QStringLiteral("changed"), this, SLOT(reloadTinting()));
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("controlBackdrop"), this, SLOT(updateBackdrop(int,QRect,QRect,QByteArray,QString)));
}

void ShellMenu::reloadTinting()
{
    const auto config = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    config->reparseConfiguration();
    m_dynamicTinting = config->group(QStringLiteral("Effect-liquidglass")).readEntry("DynamicTinting", true);
    if (!m_dynamicTinting) m_grid.clear();
    update();
}

void ShellMenu::updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &grid, const QString &role)
{
    if (!m_dynamicTinting || !isVisible() || role != QLatin1String("mttkde-shell-menu") || pid != qApp->applicationPid()
        || !windowHandle() || grid.size() != 8 * 8 * 3 || bounds.isEmpty()
        || !BackdropGeometry::sizeMatches(frame, *windowHandle())) return;
    const QPoint origin = mapToGlobal(QPoint());
    const int tolerance = BackdropGeometry::edgeTolerance(*windowHandle());
    if (qAbs(frame.x() - origin.x()) > tolerance || qAbs(frame.y() - origin.y()) > tolerance) return;
    if (grid != m_grid || m_bounds != bounds.translated(-frame.topLeft()) || palette().cacheKey() != m_sampledPalette)
        m_lastMaterial = {};
    m_bounds = bounds.translated(-frame.topLeft());
    m_sampledGeometry = QRect(origin, size());
    m_sampledScreen = screen();
    m_sampledScale = devicePixelRatioF();
    m_sampledPalette = palette().cacheKey();
    m_grid = grid;
    update();
}

void ShellMenu::paintEvent(QPaintEvent *event)
{
    if (!m_grid.isEmpty() && m_sampledGeometry == QRect(mapToGlobal(QPoint()), size())
        && m_sampledScreen && m_sampledScreen == screen() && m_sampledScale == devicePixelRatioF()
        && m_sampledPalette == palette().cacheKey()) {
        // Composite the style's actual menu panel over KWin's backdrop. It
        // includes the installed theme's fill and any saved opacity changes.
        QImage panel(8, 8, QImage::Format_ARGB32_Premultiplied);
        panel.fill(Qt::transparent);
        QStyleOption option;
        option.initFrom(this);
        {
            QPainter painter(&panel);
            painter.scale(8. / width(), 8. / height());
            style()->drawPrimitive(QStyle::PE_PanelMenu, &option, &painter, this);
        }
        const auto surfaceAt = [&](QPointF point) {
            // KWin samples cell centers. Interpolate between them so a label
            // straddling a coarse grid edge sees the same continuous backdrop.
            const double x = std::clamp((point.x() - m_bounds.x()) * 8 / m_bounds.width() - .5, 0., 7.);
            const double y = std::clamp((point.y() - m_bounds.y()) * 8 / m_bounds.height() - .5, 0., 7.);
            const int col = int(x), row = int(y);
            const auto *rgb = reinterpret_cast<const uchar *>(m_grid.constData());
            const auto channel = [&](int c) {
                const auto at = [&](int i, int j) { return rgb[(std::min(j, 7) * 8 + std::min(i, 7)) * 3 + c]; };
                return qRound(std::lerp(std::lerp(at(col, row), at(col + 1, row), x - col),
                                        std::lerp(at(col, row + 1), at(col + 1, row + 1), x - col), y - row));
            };
            const auto fill = panel.pixelColor(qBound(0, int(point.x() * 8 / width()), 7),
                                               qBound(0, int(point.y() * 8 / height()), 7));
            return GlassInk::composite(QColor(channel(0), channel(1), channel(2)), fill);
        };
        const QColor preferred = palette().color(QPalette::WindowText);
        if (panel != m_lastMaterial) {
            m_lastMaterial = panel;
            m_family = GlassInk::sample(GlassInk::component, QRectF(m_bounds).center(),
                QSizeF(m_bounds.size()) * .45, surfaceAt).family(preferred);
        }
        for (QAction *action : actions()) {
            if (!action->isVisible() || action->isSeparator()) continue;
            const QRect row = actionGeometry(action);
            const QPoint point(row.left() + row.width() / 3, row.center().y());
            const auto local = GlassInk::sample(GlassInk::menu, point,
                QSizeF(row.width() / 4., row.height() / 4.), surfaceAt);
            m_rowInks.insert(action, local.tone(preferred, m_family));
        }
    }
    QMenu::paintEvent(event);
    m_rowInks.clear();
}

void ShellMenu::initStyleOption(QStyleOptionMenuItem *option, const QAction *action) const
{
    QMenu::initStyleOption(option, action);
    if (!m_dynamicTinting) return;
    const auto sampledInk = m_rowInks.value(action);
    if (!sampledInk.isValid()) return;
    for (auto group : {QPalette::Active, QPalette::Inactive, QPalette::Disabled}) {
        QColor color = sampledInk;
        if (option->state.testFlag(QStyle::State_Selected)) {
            const auto family = GlassInk::familyOf(sampledInk);
            const auto accent = option->palette.color(group, QPalette::Highlight);
            const auto fill = selectionFill(accent, family);
            GlassInk::Samples selection;
            selection.add(fill);
            color = selection.tone(color, family);
            option->palette.setColor(group, QPalette::Highlight, fill);
        }
        if (group == QPalette::Disabled) color.setAlphaF(.48);
        for (auto role : {QPalette::WindowText, QPalette::Text, QPalette::ButtonText, QPalette::HighlightedText})
            option->palette.setColor(group, role, color);
    }
}
