/*
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/
#pragma once

#include <QApplication>
#include <QFontMetricsF>
#include <QPainter>
#include <QProxyStyle>
#include <QStyleOptionMenuItem>
#include <QWidget>
#include <QtMath>
#include <algorithm>

class SystemMenuStyle final : public QProxyStyle
{
public:
    explicit SystemMenuStyle(QObject* owner)
        : QProxyStyle(QApplication::style()->objectName())
    {
        setParent(owner);
    }

    static qreal scaleFor(const QFont& font, const QPaintDevice* device)
    {
        const qreal pixels = font.pixelSize() > 0 ? font.pixelSize()
            : font.pointSizeF() * (device ? device->logicalDpiY() : 96) / 72.0;
        return std::max(qreal(0.75), pixels / (40.0 / 3.0));
    }

    int pixelMetric(PixelMetric metric, const QStyleOption* option = nullptr,
                    const QWidget* widget = nullptr) const override
    {
        const qreal scale = scaleFor(widget ? widget->font() : QApplication::font("QMenu"), widget);
        if (metric == PM_MenuPanelWidth) return qRound(10 * scale);
        if (metric == PM_MenuHMargin || metric == PM_MenuVMargin) return 0;
        if (metric == PM_SmallIconSize) return qRound(16 * scale);
        return QProxyStyle::pixelMetric(metric, option, widget);
    }

    QSize sizeFromContents(ContentsType type, const QStyleOption* option,
                           const QSize& size, const QWidget* widget = nullptr) const override
    {
        const auto* item = qstyleoption_cast<const QStyleOptionMenuItem*>(option);
        if (type != CT_MenuItem || !item) return QProxyStyle::sizeFromContents(type, option, size, widget);
        const qreal scale = scaleFor(item->font, widget);
        if (item->menuItemType == QStyleOptionMenuItem::Separator) return QSize(1, qRound(12 * scale));
        const QFontMetricsF metrics(item->font);
        const int width = qCeil(metrics.horizontalAdvance(item->text) + 46 * scale);
        return QSize(std::max(qRound(268 * scale), width),
                     std::max(qRound(24 * scale), qCeil(metrics.height() + 4 * scale)));
    }

    void drawControl(ControlElement element, const QStyleOption* option,
                     QPainter* painter, const QWidget* widget = nullptr) const override
    {
        const auto* item = qstyleoption_cast<const QStyleOptionMenuItem*>(option);
        if (element != CE_MenuItem || !item) {
            QProxyStyle::drawControl(element, option, painter, widget);
            return;
        }
        const qreal scale = scaleFor(item->font, widget);
        const QRectF rect(item->rect);
        painter->save();
        painter->setRenderHint(QPainter::Antialiasing);
        if (item->menuItemType == QStyleOptionMenuItem::Separator) {
            QColor line = item->palette.color(QPalette::WindowText);
            line.setAlphaF(0.14);
            painter->setPen(QPen(line, 1));
            painter->drawLine(QPointF(rect.left() + 12 * scale, rect.center().y()),
                              QPointF(rect.right() - 12 * scale, rect.center().y()));
            painter->restore();
            return;
        }
        const bool selected = item->state.testFlag(State_Selected);
        const bool enabled = item->state.testFlag(State_Enabled);
        const auto group = enabled ? QPalette::Active : QPalette::Disabled;
        if (selected) {
            painter->setPen(Qt::NoPen);
            painter->setBrush(item->palette.brush(group, QPalette::Highlight));
            painter->drawRoundedRect(rect, 6 * scale, 6 * scale);
        }
        const int iconSize = qRound(16 * scale);
        const QRect iconRect = visualRect(item->direction, item->rect,
            QRect(item->rect.left() + qRound(12 * scale),
                  qRound(rect.center().y() - iconSize / 2.0), iconSize, iconSize));
        item->icon.paint(painter, iconRect, Qt::AlignCenter,
                         !enabled ? QIcon::Disabled : selected ? QIcon::Selected : QIcon::Normal);
        const QRect textRect = visualRect(item->direction, item->rect,
            item->rect.adjusted(qRound(34 * scale), 0, -qRound(12 * scale), 0));
        painter->setFont(item->font);
        painter->setPen(item->palette.color(group, selected ? QPalette::HighlightedText : QPalette::WindowText));
        painter->drawText(textRect, Qt::AlignVCenter | Qt::AlignLeading | Qt::TextHideMnemonic, item->text);
        painter->restore();
    }
};
