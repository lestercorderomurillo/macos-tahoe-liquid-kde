// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Lester Cordero Murillo
#include <QApplication>
#include <QMenu>
#include <QPainter>
#include <QPainterPath>
#include <QProxyStyle>
#include <QSettings>
#include <QStandardPaths>
#include <QStyleFactory>
#include <QStyleOption>
#include <QStylePlugin>
#include <QWindow>
#include <KWindowEffects>
#include <cmath>

namespace {
// Fit to the outer contours of the real 2x macOS 26/27 Finder menus.
// Keep the corner extent independent of the 5px content inset.
QPainterPath contour(const QRectF &rect)
{
    const qreal r = qMin(qreal(17), qMin(rect.width(), rect.height()) / 2);
    QPainterPath path;
    for (int corner = 0; corner < 4; ++corner) {
        const QPointF center(corner == 0 || corner == 1 ? rect.right()-r : rect.left()+r,
                             corner == 0 || corner == 3 ? rect.top()+r : rect.bottom()-r);
        for (int i = 0; i <= 64; ++i) {
            const qreal a = (-90 + corner*90 + i*90.0/64) * M_PI/180;
            const auto power = [](qreal x) { return std::copysign(std::pow(std::abs(x), 2.0/3.1), x); };
            const QPointF p = center + QPointF(r*power(std::cos(a)), r*power(std::sin(a)));
            if (corner == 0 && i == 0) path.moveTo(p); else path.lineTo(p);
        }
    }
    path.closeSubpath();
    return path;
}

class MenuStyle final : public QProxyStyle {
public:
    explicit MenuStyle(QStyle *base) : QProxyStyle(base) {}
    bool themed(const QWidget *widget) const {
        if (!qobject_cast<const QMenu *>(widget) || widget->testAttribute(Qt::WA_StyleSheetTarget)) return false;
        const auto config = QStandardPaths::writableLocation(QStandardPaths::ConfigLocation);
        QSettings settings(config + "/Kvantum/kvantum.kvconfig", QSettings::IniFormat);
        return settings.value("theme").toString().startsWith("mac-tahoe-liquid-kde");
    }
    int pixelMetric(PixelMetric metric, const QStyleOption *option, const QWidget *widget) const override {
        const int value = QProxyStyle::pixelMetric(metric, option, widget);
        if (themed(widget) && (metric == PM_MenuHMargin || metric == PM_MenuVMargin))
            return qMax(0, value - 4); // bundled frame 9px -> reference content inset 5px
        return value;
    }
    void drawPrimitive(PrimitiveElement element, const QStyleOption *option,
                       QPainter *painter, const QWidget *widget) const override {
        if (element != PE_PanelMenu || !themed(widget)) {
            QProxyStyle::drawPrimitive(element, option, painter, widget);
            return;
        }
        // Let Kvantum resolve the actual material, including edition, opacity,
        // compositing fallback and active light/dark profile. Sample its interior.
        QImage sample(1, 1, QImage::Format_ARGB32_Premultiplied);
        sample.fill(Qt::transparent);
        {
            QPainter probe(&sample);
            probe.translate(-option->rect.center());
            baseStyle()->drawPrimitive(element, option, &probe, widget);
        }
        const bool translucent = widget->testAttribute(Qt::WA_TranslucentBackground);
        const int margin = baseStyle()->pixelMetric(PM_MenuHMargin, option, widget);
        const qreal shadow = translucent ? qMax(0, margin - 9) : 0;
        const QRectF surface = QRectF(option->rect).adjusted(shadow, shadow, -shadow, -shadow);
        const QPainterPath shape = contour(surface);
        painter->save();
        painter->setRenderHint(QPainter::Antialiasing);
        painter->setCompositionMode(QPainter::CompositionMode_Source);
        painter->fillRect(option->rect, Qt::transparent);
        painter->setCompositionMode(QPainter::CompositionMode_SourceOver);
        if (shadow > 0) {
            for (int i = int(shadow); i > 0; --i) {
                const auto outer = contour(surface.adjusted(-i, -i, i, i));
                painter->fillPath(outer.subtracted(shape), QColor(0, 0, 0, 8));
            }
        }
        painter->fillPath(shape, sample.pixelColor(0, 0));
        const auto inner = contour(surface.adjusted(.75, .75, -.75, -.75));
        painter->fillPath(shape.subtracted(inner), QColor(0, 0, 0, 46));
        painter->fillPath(inner.subtracted(contour(surface.adjusted(1.5, 1.5, -1.5, -1.5))), QColor(255, 255, 255, 56));
        painter->restore();
        if (translucent && widget->windowHandle())
            KWindowEffects::enableBlurBehind(widget->windowHandle(), true, QRegion(shape.toFillPolygon().toPolygon()));
    }
};
}

class MenuStylePlugin final : public QStylePlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QStyleFactoryInterface" FILE "menu_style.json")
public:
    QStyle *create(const QString &key) override {
        if (key.compare("MacTahoe", Qt::CaseInsensitive) != 0) return nullptr;
        auto *base = QStyleFactory::create("kvantum");
        return base ? new MenuStyle(base) : nullptr;
    }
};
#include "menu_style.moc"
