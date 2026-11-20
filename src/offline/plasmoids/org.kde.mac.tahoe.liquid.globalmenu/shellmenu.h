// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QMenu>
#include <QPainter>
#include <QPaintEvent>
#include <QStyleOptionMenuItem>
#include <QWidgetAction>

// A bright window can show through the dark glass. Give the light lettering
// a narrow shadow using the actual style's glyphs, shortcuts and arrow mask.
class ShellMenu final : public QMenu
{
public:
    using QMenu::QMenu;

protected:
    void paintEvent(QPaintEvent *event) override
    {
        QMenu::paintEvent(event);
        if (!testAttribute(Qt::WA_TranslucentBackground)
            || palette().color(QPalette::WindowText).lightnessF() < 0.5) return;

        QPainter painter(this);
        const qreal scale = devicePixelRatioF();
        for (auto *action : actions()) {
            const QRect rect = actionGeometry(action);
            if (action->isSeparator() || action == activeAction() || qobject_cast<QWidgetAction *>(action)
                || !event->region().intersects(rect)) continue;

            QStyleOptionMenuItem option;
            initStyleOption(&option, action);
            option.rect = rect;
            QPixmap row(rect.size() * scale);
            row.setDevicePixelRatio(scale);
            row.fill(Qt::transparent);
            {
                QPainter glyphs(&row);
                glyphs.translate(-rect.topLeft());
                style()->drawControl(QStyle::CE_MenuItem, &option, &glyphs, this);
            }
            QPixmap shadow = row;
            {
                QPainter tint(&shadow);
                tint.setCompositionMode(QPainter::CompositionMode_SourceIn);
                tint.fillRect(QRect(QPoint(), rect.size()), QColor(0, 0, 0, 155));
            }
            for (const QPointF offset : {QPointF(-0.6, 0), QPointF(0.6, 0), QPointF(0, -0.5), QPointF(0, 0.85)})
                painter.drawPixmap(QPointF(rect.topLeft()) + offset, shadow);
            painter.drawPixmap(rect.topLeft(), row);
        }
    }
};
