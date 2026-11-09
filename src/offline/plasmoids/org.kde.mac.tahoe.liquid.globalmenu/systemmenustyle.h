/*
    SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/
#pragma once

#include <QApplication>
#include <QKeySequence>
#include <QMenu>
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
        const QString label = item->text.section(QLatin1Char('\t'), 0, 0);
        const QString shortcut = shortcutSymbols(item->text.section(QLatin1Char('\t'), 1));
        const qreal shortcutWidth = shortcut.isEmpty() ? 0 : metrics.horizontalAdvance(shortcut) + 24 * scale;
        const int width = qCeil(metrics.horizontalAdvance(label) + shortcutWidth
                               + (item->icon.isNull() ? 24 : 46) * scale);
        // QMenu adds its native shortcut column after measuring every row.
        // We already measured the compact symbols, so cancel that extra width.
        int nativeShortcutWidth = 0;
        if (const auto* menu = qobject_cast<const QMenu*>(widget)) {
            const QFontMetrics menuMetrics(menu->font());
            for (const auto* action : menu->actions()) {
                if (!action->isVisible() || action->isSeparator()) continue;
                const QString hint = action->text().contains(QLatin1Char('\t'))
                    ? action->text().section(QLatin1Char('\t'), 1)
                    : action->shortcut().toString(QKeySequence::NativeText);
                nativeShortcutWidth = std::max(nativeShortcutWidth, menuMetrics.horizontalAdvance(hint));
            }
        }
        return QSize(std::max(qRound(268 * scale), width) - nativeShortcutWidth,
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
        const QString label = item->text.section(QLatin1Char('\t'), 0, 0);
        const QString shortcut = shortcutSymbols(item->text.section(QLatin1Char('\t'), 1));
        const int shortcutWidth = qCeil(QFontMetricsF(item->font).horizontalAdvance(shortcut));
        const int trailing = qRound(12 * scale) + (shortcut.isEmpty() ? 0 : shortcutWidth + qRound(24 * scale));
        const QRect textRect = visualRect(item->direction, item->rect,
            item->rect.adjusted(qRound((item->icon.isNull() ? 12 : 34) * scale), 0, -trailing, 0));
        painter->setFont(item->font);
        painter->setPen(foreground);
        painter->drawText(textRect, Qt::AlignVCenter | Qt::AlignLeading | Qt::TextHideMnemonic, label);
        if (!shortcut.isEmpty()) {
            const QRect shortcutRect = visualRect(item->direction, item->rect,
                QRect(item->rect.right() + 1 - qRound(12 * scale) - shortcutWidth,
                      item->rect.top(), shortcutWidth, item->rect.height()));
            QColor hint = foreground;
            if (!selected && enabled) hint.setAlphaF(0.55);
            painter->setPen(hint);
            painter->drawText(shortcutRect, Qt::AlignVCenter | Qt::AlignRight, shortcut);
        }
        painter->restore();
    }
    static QString shortcutSymbols(const QString& shortcut)
    {
        const auto sequence = QKeySequence::fromString(shortcut, QKeySequence::NativeText);
        if (sequence == QKeySequence(Qt::CTRL | Qt::META | Qt::Key_Q)) return QStringLiteral("⌃⌘Q");
        if (sequence == QKeySequence(Qt::SHIFT | Qt::META | Qt::Key_Q)) return QStringLiteral("⇧⌘Q");
        return shortcut;
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
        painter->setPen(QPen(color, 1.0, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
        painter->setBrush(Qt::NoBrush);
        if (name == QLatin1String("computer")) {
            painter->drawRoundedRect(QRectF(3, 4, 10, 7.5), 0.65, 0.65);
            painter->drawLine(QPointF(1, 12), QPointF(15, 12));
        } else if (name == QLatin1String("preferences-system")) {
            QPainterPath gear;
            for (int i = 0; i < 40; ++i) {
                const qreal angle = i * 2 * 3.141592653589793 / 40;
                const qreal radius = i % 4 == 1 || i % 4 == 2 ? 5.5 : 4.7;
                const QPointF point(8 + radius * std::cos(angle), 8 + radius * std::sin(angle));
                if (i == 0) gear.moveTo(point); else gear.lineTo(point);
            }
            gear.closeSubpath();
            painter->drawPath(gear);
            painter->drawEllipse(QPointF(8, 8), 3.4, 3.4);
        } else {
            painter->setPen(QPen(color, 1.35, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
            painter->drawLine(QPointF(4.1, 12.5), QPointF(9.1, 3.5));
            painter->drawLine(QPointF(7, 3.5), QPointF(12, 12.5));
            painter->drawLine(QPointF(2.6, 9.7), QPointF(13.4, 9.7));
        }
        painter->restore();
        return true;
    }
};
