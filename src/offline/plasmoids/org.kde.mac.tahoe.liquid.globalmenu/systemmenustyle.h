/*
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/
#pragma once

#include <QApplication>
#include <QFontMetricsF>
#include <QPainter>
#include <QPainterPath>
#include <cmath>
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
        const int width = qCeil(metrics.horizontalAdvance(item->text) + (item->icon.isNull() ? 24 : 46) * scale);
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
        const QColor foreground = item->palette.color(group, selected ? QPalette::HighlightedText : QPalette::WindowText);
        if (!drawReferenceIcon(item->icon.name(), painter, iconRect, foreground)) {
            item->icon.paint(painter, iconRect, Qt::AlignCenter,
                             !enabled ? QIcon::Disabled : selected ? QIcon::Selected : QIcon::Normal);
        }
        const QRect textRect = visualRect(item->direction, item->rect,
            item->rect.adjusted(qRound((item->icon.isNull() ? 12 : 34) * scale), 0, -qRound(12 * scale), 0));
        painter->setFont(item->font);
        painter->setPen(item->palette.color(group, selected ? QPalette::HighlightedText : QPalette::WindowText));
        painter->drawText(textRect, Qt::AlignVCenter | Qt::AlignLeading | Qt::TextHideMnemonic, item->text);
        painter->restore();
    }
private:
    static bool drawReferenceIcon(const QString& name, QPainter* painter,
                                  const QRect& rect, const QColor& color)
    {
        if (name != QLatin1String("computer") && name != QLatin1String("preferences-system")
            && name != QLatin1String("software-store-symbolic")) return false;
        painter->save();
        painter->translate(rect.topLeft());
        painter->scale(rect.width() / 16.0, rect.height() / 16.0);
        painter->setPen(QPen(color, 1.15, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
        painter->setBrush(Qt::NoBrush);
        if (name == QLatin1String("computer")) {
            painter->drawRoundedRect(QRectF(2.5, 3.5, 11, 8), 0.8, 0.8);
            painter->drawLine(QPointF(0.8, 12.5), QPointF(15.2, 12.5));
        } else if (name == QLatin1String("preferences-system")) {
            QPainterPath gear;
            for (int i = 0; i < 48; ++i) {
                const qreal angle = i * 2 * 3.141592653589793 / 48;
                const qreal radius = i % 4 == 1 || i % 4 == 2 ? 6.1 : 5.1;
                const QPointF point(8 + radius * std::cos(angle), 8 + radius * std::sin(angle));
                if (i == 0) gear.moveTo(point); else gear.lineTo(point);
            }
            gear.closeSubpath();
            painter->drawPath(gear);
            painter->drawEllipse(QPointF(8, 8), 3.6, 3.6);
        } else {
            painter->setPen(QPen(color, 1.6, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
            painter->drawLine(QPointF(4, 13), QPointF(9.2, 3));
            painter->drawLine(QPointF(7, 3), QPointF(12.2, 13));
            painter->drawLine(QPointF(2, 10), QPointF(14, 10));
        }
        painter->restore();
        return true;
    }
};
