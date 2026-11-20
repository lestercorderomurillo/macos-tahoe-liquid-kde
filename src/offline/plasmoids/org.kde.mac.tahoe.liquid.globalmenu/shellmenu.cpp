// SPDX-License-Identifier: GPL-2.0-or-later
#include "shellmenu.h"
#include "../org.kde.mac.tahoe.liquid.taskmanager/launcher/glassink.h"
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
    m_bounds = bounds.translated(-frame.topLeft());
    m_grid = grid;
    update();
}

void ShellMenu::hideEvent(QHideEvent *event)
{
    m_grid.clear();
    QMenu::hideEvent(event);
}

void ShellMenu::paintEvent(QPaintEvent *event)
{
    if (!m_grid.isEmpty()) {
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
        for (QAction *action : actions()) {
            if (!action->isVisible() || action->isSeparator()) continue;
            const QRect row = actionGeometry(action);
            const QPoint point(row.left() + row.width() / 3, row.center().y());
            const auto surfaceAt = [&](QPointF p) {
                const int col = qBound(0, int((p.x() - m_bounds.x()) * 8 / m_bounds.width()), 7);
                const int line = qBound(0, int((p.y() - m_bounds.y()) * 8 / m_bounds.height()), 7);
                const auto *rgb = reinterpret_cast<const uchar *>(m_grid.constData()) + (line * 8 + col) * 3;
                const auto fill = panel.pixelColor(qBound(0, int(p.x() * 8 / width()), 7),
                                                   qBound(0, int(p.y() * 8 / height()), 7));
                return GlassInk::composite(QColor(rgb[0], rgb[1], rgb[2]), fill);
            };
            m_rowInks.insert(action, GlassInk::sample(Qt::white, point,
                QSizeF(row.width() / 4., row.height()), surfaceAt));
        }
    }
    QMenu::paintEvent(event);
    m_rowInks.clear();
}

void ShellMenu::initStyleOption(QStyleOptionMenuItem *option, const QAction *action) const
{
    QMenu::initStyleOption(option, action);
    if (!m_dynamicTinting || option->state.testFlag(QStyle::State_Selected)) return;
    const auto sampledInk = m_rowInks.value(action);
    if (!sampledInk.isValid()) return;
    for (auto group : {QPalette::Active, QPalette::Inactive, QPalette::Disabled}) {
        for (auto role : {QPalette::WindowText, QPalette::Text, QPalette::ButtonText}) {
            QColor color = sampledInk;
            if (group == QPalette::Disabled) color.setAlphaF(.48);
            option->palette.setColor(group, role, color);
        }
    }
}
