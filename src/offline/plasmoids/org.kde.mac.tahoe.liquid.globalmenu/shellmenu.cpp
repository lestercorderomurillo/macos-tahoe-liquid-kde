// SPDX-License-Identifier: GPL-2.0-or-later
#include "shellmenu.h"
#include "../org.kde.mac.tahoe.liquid.taskmanager/launcher/backdropgeometry.h"
#include <QApplication>
#include <QDBusConnection>
#include <QPainter>
#include <QWindow>
#include <algorithm>
#include <cmath>

namespace {
double luminance(const QColor &c)
{
    const auto linear = [](double x) { return x <= .04045 ? x / 12.92 : std::pow((x + .055) / 1.055, 2.4); };
    return .2126 * linear(c.redF()) + .7152 * linear(c.greenF()) + .0722 * linear(c.blueF());
}

QColor ink(const QColor &base, const QColor &background)
{
    const double offset = luminance(base) > .5 ? .4 : 0.;
    QColor preferred = QColor::fromRgbF(.6 * base.redF() + offset, .6 * base.greenF() + offset,
                                        .6 * base.blueF() + offset, base.alphaF());
    if (!background.isValid()) return preferred;
    const double bg = luminance(background) + .05;
    const double fg = luminance(preferred) + .05;
    if (std::max(bg, fg) / std::min(bg, fg) >= 4.5) return preferred;
    return bg / .05 >= 1.05 / bg ? Qt::black : Qt::white;
}
}

ShellMenu::ShellMenu(QWidget *parent) : QMenu(parent)
{
    setProperty("_mttkde_shell_menu", true);
    QDBusConnection::sessionBus().connect(QStringLiteral("org.kde.KWin"),
        QStringLiteral("/org/kde/MacTahoe/Glass"), QStringLiteral("org.kde.MacTahoe.Glass"),
        QStringLiteral("controlBackdrop"), this, SLOT(updateBackdrop(int,QRect,QRect,QByteArray,QString)));
}

void ShellMenu::updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &grid, const QString &role)
{
    if (!isVisible() || role != QLatin1String("mttkde-shell-menu") || pid != qApp->applicationPid()
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
            const int col = qBound(0, (point.x() - m_bounds.x()) * 8 / m_bounds.width(), 7);
            const int line = qBound(0, (point.y() - m_bounds.y()) * 8 / m_bounds.height(), 7);
            const auto *rgb = reinterpret_cast<const uchar *>(m_grid.constData()) + (line * 8 + col) * 3;
            const QColor fill = panel.pixelColor(qBound(0, point.x() * 8 / width(), 7), qBound(0, point.y() * 8 / height(), 7));
            const double a = fill.alphaF();
            m_rowBackgrounds.insert(action, QColor::fromRgbF(fill.redF() * a + rgb[0] / 255. * (1 - a),
                fill.greenF() * a + rgb[1] / 255. * (1 - a), fill.blueF() * a + rgb[2] / 255. * (1 - a)));
        }
    }
    QMenu::paintEvent(event);
    m_rowBackgrounds.clear();
}

void ShellMenu::initStyleOption(QStyleOptionMenuItem *option, const QAction *action) const
{
    QMenu::initStyleOption(option, action);
    if (option->state.testFlag(QStyle::State_Selected)) return;
    const auto background = m_rowBackgrounds.value(action);
    for (auto group : {QPalette::Active, QPalette::Inactive, QPalette::Disabled}) {
        for (auto role : {QPalette::WindowText, QPalette::Text, QPalette::ButtonText}) {
            QColor color = ink(option->palette.color(group, role), background);
            if (group == QPalette::Disabled && background.isValid()) color.setAlphaF(.48);
            option->palette.setColor(group, role, color);
        }
    }
}
