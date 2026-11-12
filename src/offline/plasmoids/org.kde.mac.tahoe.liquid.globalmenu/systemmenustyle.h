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
#include <QIconEngine>
#include <QSettings>
#include <QStandardPaths>
#include <cmath>
#include <QCommonStyle>
#include <QStyleOptionMenuItem>
#include <QWidget>
#include <QtMath>
#include <algorithm>

class SystemMenuStyle final : public QCommonStyle
{
public:
    enum class Preset { Tahoe, GoldenGate };

    static Preset themePreset()
    {
        QSettings settings(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
                           + QStringLiteral("/kdeglobals"), QSettings::IniFormat);
        settings.sync();
        return settings.value(QStringLiteral("MacTahoeLiquidKde/SystemMenuPreset")).toString() == QLatin1String("golden-gate")
            ? Preset::GoldenGate : Preset::Tahoe;
    }

    static QIcon menuIcon(const QString& chosen, const QString& fallback, Preset preset)
    {
        // Golden Gate keeps only the first three symbols; Tahoe labels every
        // action. Visibility belongs to the active edition, not its launcher.
        if (preset == Preset::GoldenGate && fallback != QLatin1String("computer")
            && fallback != QLatin1String("preferences-system")
            && fallback != QLatin1String("software-store-symbolic")) return {};
        if (chosen != fallback) return QIcon::fromTheme(chosen);
        return QIcon(new ReferenceIconEngine(fallback));
    }

    explicit SystemMenuStyle(QObject* owner)
    {
        setParent(owner);
    }

    // Only menu rows and their metrics are custom. Never clone or own the
    // application style: Kvantum caches literal SVG fills, and the desktop's
    // light/dark style cycle replaces that instance without updating a clone.
    void drawPrimitive(PrimitiveElement element, const QStyleOption* option,
                       QPainter* painter, const QWidget* widget = nullptr) const override
    {
        QApplication::style()->drawPrimitive(element, option, painter, widget);
    }

    int styleHint(StyleHint hint, const QStyleOption* option = nullptr,
                  const QWidget* widget = nullptr, QStyleHintReturn* result = nullptr) const override
    {
        return QApplication::style()->styleHint(hint, option, widget, result);
    }

    void polish(QWidget* widget) override { QApplication::style()->polish(widget); }
    void unpolish(QWidget* widget) override { QApplication::style()->unpolish(widget); }
    void polish(QPalette& palette) override { QApplication::style()->polish(palette); }
    QPalette standardPalette() const override { return QApplication::style()->standardPalette(); }

    QRect subElementRect(SubElement element, const QStyleOption* option,
                         const QWidget* widget = nullptr) const override
    {
        return QApplication::style()->subElementRect(element, option, widget);
    }

    QIcon standardIcon(StandardPixmap icon, const QStyleOption* option = nullptr,
                       const QWidget* widget = nullptr) const override
    {
        return QApplication::style()->standardIcon(icon, option, widget);
    }

    QPixmap standardPixmap(StandardPixmap icon, const QStyleOption* option = nullptr,
                           const QWidget* widget = nullptr) const override
    {
        return QApplication::style()->standardPixmap(icon, option, widget);
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
        return QApplication::style()->pixelMetric(metric, option, widget);
    }

    QSize sizeFromContents(ContentsType type, const QStyleOption* option,
                           const QSize& size, const QWidget* widget = nullptr) const override
    {
        const auto* item = qstyleoption_cast<const QStyleOptionMenuItem*>(option);
        if (type != CT_MenuItem || !item) return QApplication::style()->sizeFromContents(type, option, size, widget);
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
            QApplication::style()->drawControl(element, option, painter, widget);
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
    class ReferenceIconEngine final : public QIconEngine {
        QString m_name;
    public:
        explicit ReferenceIconEngine(QString name) : m_name(std::move(name)) {}
        QIconEngine* clone() const override { return new ReferenceIconEngine(m_name); }
        QString iconName() override { return m_name; }
        void paint(QPainter* painter, const QRect& rect, QIcon::Mode mode, QIcon::State) override
        {
            const auto group = mode == QIcon::Disabled ? QPalette::Disabled : QPalette::Active;
            const auto role = mode == QIcon::Selected ? QPalette::HighlightedText : QPalette::WindowText;
            drawReferenceIcon(m_name, painter, rect, QApplication::palette().color(group, role));
        }
    };

    static bool drawReferenceIcon(const QString& name, QPainter* painter,
                                  const QRect& rect, const QColor& color)
    {
        static const QStringList names = {QStringLiteral("computer"), QStringLiteral("preferences-system"),
            QStringLiteral("software-store-symbolic"), QStringLiteral("dialog-cancel"),
            QStringLiteral("system-suspend"), QStringLiteral("system-reboot"),
            QStringLiteral("system-shutdown"), QStringLiteral("system-lock-screen"), QStringLiteral("user-identity")};
        if (!names.contains(name)) return false;
        painter->save();
        painter->translate(rect.topLeft());
        painter->scale(rect.width() / 16.0, rect.height() / 16.0);
        painter->setPen(QPen(color, 1.0, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
        painter->setBrush(Qt::NoBrush);
        if (name == QLatin1String("computer")) {
            painter->drawRoundedRect(QRectF(3, 4, 10, 7.5), 0.65, 0.65);
            painter->drawLine(QPointF(1, 12), QPointF(15, 12));
        } else if (name == QLatin1String("preferences-system")) {
            // The macOS menu symbol is an 18-tooth wheel with a hollow hub
            // and three spokes, rather than the generic hollow gear outline.
            QPainterPath gear;
            for (int i = 0; i < 72; ++i) {
                const qreal angle = (i - 0.5) * 2 * 3.141592653589793 / 72;
                const qreal radius = i % 4 < 2 ? 5.8 : 5.1;
                const QPointF point(8 + radius * std::cos(angle), 8 + radius * std::sin(angle));
                if (i == 0) gear.moveTo(point); else gear.lineTo(point);
            }
            gear.closeSubpath();
            gear.addEllipse(QPointF(8, 8), 4.15, 4.15);
            gear.addEllipse(QPointF(8, 8), 1.5, 1.5);
            gear.addEllipse(QPointF(8, 8), 0.65, 0.65);
            painter->setPen(Qt::NoPen);
            painter->setBrush(color);
            painter->drawPath(gear);
            painter->setPen(QPen(color, 0.9, Qt::SolidLine, Qt::RoundCap));
            for (int spoke = 0; spoke < 3; ++spoke) {
                const qreal angle = spoke * 2 * 3.141592653589793 / 3;
                const QPointF direction(std::cos(angle), std::sin(angle));
                painter->drawLine(QPointF(8, 8) + 1.2 * direction,
                                  QPointF(8, 8) + 4.5 * direction);
            }
        } else if (name == QLatin1String("software-store-symbolic")) {
            painter->setPen(QPen(color, 1.35, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
            painter->drawLine(QPointF(4.1, 12.5), QPointF(9.1, 3.5));
            painter->drawLine(QPointF(7, 3.5), QPointF(12, 12.5));
            painter->drawLine(QPointF(2.6, 9.7), QPointF(13.4, 9.7));
        } else if (name == QLatin1String("dialog-cancel")) {
            QPainterPath octagon;
            octagon.moveTo(5.7, 2.5); octagon.lineTo(10.3, 2.5);
            octagon.lineTo(13.5, 5.7); octagon.lineTo(13.5, 10.3);
            octagon.lineTo(10.3, 13.5); octagon.lineTo(5.7, 13.5);
            octagon.lineTo(2.5, 10.3); octagon.lineTo(2.5, 5.7); octagon.closeSubpath();
            painter->drawPath(octagon);
            painter->drawLine(QPointF(6, 6), QPointF(10, 10));
            painter->drawLine(QPointF(10, 6), QPointF(6, 10));
        } else if (name == QLatin1String("system-suspend")) {
            painter->drawEllipse(QPointF(8, 8), 5.1, 5.1);
            painter->drawLine(QPointF(3.2, 8), QPointF(12.8, 8));
        } else if (name == QLatin1String("system-reboot")) {
            QPainterPath triangle;
            triangle.moveTo(4.2, 8); triangle.lineTo(11.5, 3.7);
            triangle.lineTo(11.5, 12.3); triangle.closeSubpath();
            painter->drawPath(triangle);
        } else if (name == QLatin1String("system-shutdown")) {
            painter->drawArc(QRectF(3, 3, 10, 10), 135 * 16, 270 * 16);
            painter->drawLine(QPointF(8, 2), QPointF(8, 7.4));
        } else if (name == QLatin1String("system-lock-screen")) {
            painter->drawRoundedRect(QRectF(4, 7, 8, 6), 0.8, 0.8);
            QPainterPath shackle;
            shackle.moveTo(5.5, 7); shackle.lineTo(5.5, 5.2);
            shackle.cubicTo(5.5, 2, 10.5, 2, 10.5, 5.2); shackle.lineTo(10.5, 7);
            painter->drawPath(shackle);
        } else if (name == QLatin1String("user-identity")) {
            painter->drawEllipse(QPointF(8, 8), 5.1, 5.1);
            painter->setBrush(color);
            painter->drawEllipse(QPointF(8, 6.5), 1.3, 1.3);
            QPainterPath shoulders;
            shoulders.moveTo(4.1, 11.3); shoulders.cubicTo(4.5, 8.5, 11.5, 8.5, 11.9, 11.3);
            shoulders.quadTo(8, 14.5, 4.1, 11.3);
            painter->drawPath(shoulders);
        }
        painter->restore();
        return true;
    }
};
