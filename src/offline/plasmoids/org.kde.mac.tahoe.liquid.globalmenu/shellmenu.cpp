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
    const auto group = config->group(QStringLiteral("Effect-liquidglass"));
    m_dynamicTinting = group.readEntry("DynamicTinting", true);
    const auto saved = group.readEntry("AdaptiveContrastPreset", QByteArray());
    QJsonObject profiles;
    if (ContrastPreset::resolve(saved.isEmpty() ? ContrastPreset::empty() : QJsonDocument::fromJson(saved).object(), profiles).isEmpty())
        m_profile = profiles.value(QStringLiteral("menu.native")).toObject();
    if (!m_dynamicTinting) m_grid.clear();
    update();
}

void ShellMenu::updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &grid, const QString &role)
{
    if (!m_dynamicTinting || !isVisible() || role != QLatin1String("mttkde-shell-menu") || pid != qApp->applicationPid()
        || !windowHandle() || (grid.size() != 8 * 8 * 3 && grid.size() != 64 * 64 * 3) || bounds.isEmpty()
        || !BackdropGeometry::sizeMatches(frame, *windowHandle())) return;
    const QPoint origin = mapToGlobal(QPoint());
    const int tolerance = BackdropGeometry::edgeTolerance(*windowHandle());
    if (qAbs(frame.x() - origin.x()) > tolerance || qAbs(frame.y() - origin.y()) > tolerance) return;
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
        const int side = m_grid.size() == 64 * 64 * 3 ? 64 : 8;
        QImage panel(side, side, QImage::Format_ARGB32_Premultiplied);
        panel.fill(Qt::transparent);
        QStyleOption option;
        option.initFrom(this);
        {
            QPainter painter(&panel);
            painter.scale(double(side) / width(), double(side) / height());
            style()->drawPrimitive(QStyle::PE_PanelMenu, &option, &painter, this);
        }
        const auto surfaceAt = [&](QPointF point) {
            // KWin samples cell centers. Interpolate between them so a label
            // straddling a coarse grid edge sees the same continuous backdrop.
            const double x = std::clamp((point.x() - m_bounds.x()) * side / m_bounds.width() - .5, 0., double(side - 1));
            const double y = std::clamp((point.y() - m_bounds.y()) * side / m_bounds.height() - .5, 0., double(side - 1));
            const int col = int(x), row = int(y);
            const auto *rgb = reinterpret_cast<const uchar *>(m_grid.constData());
            const auto channel = [&](int c) {
                const auto at = [&](int i, int j) { return rgb[(std::min(j, side - 1) * side + std::min(i, side - 1)) * 3 + c]; };
                return qRound(std::lerp(std::lerp(at(col, row), at(col + 1, row), x - col),
                                        std::lerp(at(col, row + 1), at(col + 1, row + 1), x - col), y - row));
            };
            const auto fill = panel.pixelColor(qBound(0, int(point.x() * side / width()), side - 1),
                                               qBound(0, int(point.y() * side / height()), side - 1));
            return GlassInk::composite(QColor(channel(0), channel(1), channel(2)), fill);
        };
        m_actionSamples.clear();
        for (auto *action : actions()) {
            const QRect row = actionGeometry(action);
            if (row.isEmpty() || action->isSeparator()) continue;
            const QString label = action->text().section(QLatin1Char('\t'), 0, 0);
            const int textWidth = std::min(row.width(), fontMetrics().horizontalAdvance(label));
            const int inset = style()->pixelMetric(QStyle::PM_SmallIconSize) + 8;
            const QRect text = style()->visualRect(layoutDirection(), row,
                QRect(row.left() + inset, row.top(), textWidth, row.height()));
            const auto scope = m_profile.value(QStringLiteral("scope")).toString();
            const auto bounds = scope == QLatin1String("component") ? rect() : scope == QLatin1String("line") ? text : row;
            GlassInk::Samples samples;
            GlassInk::zonePoints(bounds, m_profile.value(QStringLiteral("sampleCount")).toInt(15),
                [&](QPointF point) { samples.add(surfaceAt(point)); });
            m_actionSamples.insert(action, samples);
        }
        m_paintingSampledMenu = true;
    }
    QMenu::paintEvent(event);
    m_paintingSampledMenu = false;
}

void ShellMenu::initStyleOption(QStyleOptionMenuItem *option, const QAction *action) const
{
    QMenu::initStyleOption(option, action);
    if (!m_dynamicTinting || !m_paintingSampledMenu || option->state.testFlag(QStyle::State_Selected)) return;
    for (auto group : {QPalette::Active, QPalette::Inactive, QPalette::Disabled}) {
        const QColor base = option->palette.color(group, QPalette::Text);
        option->palette.setColor(group, QPalette::Text, m_actionSamples.value(action).tone(base, ContrastPreset::settings(m_profile)));
    }
}
