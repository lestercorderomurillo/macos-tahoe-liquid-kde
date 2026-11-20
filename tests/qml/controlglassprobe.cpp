// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include <QGuiApplication>
#include <QVariantMap>
#include <limits>
#include <iostream>

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    const auto rect = [](double x, double y, double w, double h, double r) {
        return QVariantMap{{"x", x}, {"y", y}, {"width", w}, {"height", h}, {"radius", r}};
    };
    const auto region = ControlGlass::regionFor({rect(0,0,64,64,32),rect(80,0,140,64,32)});
    if (!region.contains(QPoint(32,32)) || !region.contains(QPoint(150,32))
        || region.contains(QPoint(70,32)) || region.contains(QPoint(1,1))) return 1;
    if (!ControlGlass::regionFor({rect(0,0,-1,4,0),rect(0,0,4,4,std::numeric_limits<double>::quiet_NaN())}).isEmpty()) return 2;
    if (!ControlGlass::regionFor({rect(0,0,64,64,1000)}).contains(QPoint(32,32))) return 3;
    QWindow window;
    ControlGlass glass;
    glass.setWindow(&window);
    glass.setSurfaces({rect(10,10,64,64,32)});
    if (!window.mask().contains(QPoint(42,42)) || window.mask().contains(QPoint(0,0))) return 4;
    glass.setSurfaces({rect(80,10,64,64,32)});
    if (window.mask().contains(QPoint(42,42)) || !window.mask().contains(QPoint(112,42))) return 5;
    glass.setMaskWindow(false);
    if (!window.mask().isEmpty() || glass.surfaces().size() != 1) return 6;
    glass.setMaskWindow(true);
    if (!window.mask().contains(QPoint(112,42)) || window.mask().contains(QPoint(0,0))) return 7;
    window.setTitle(QStringLiteral("mttkde-apps"));
    window.setGeometry(10, 10, 420, 250);
    window.show();
    const auto sample = [&](QSize size, char channel) {
        const QRect frame(window.position(), size);
        const QByteArray colors(8 * 8 * 3, channel);
        return QMetaObject::invokeMethod(&glass, "updateBackdrop", Qt::DirectConnection,
            Q_ARG(int, int(app.applicationPid())), Q_ARG(QRect, frame), Q_ARG(QRect, frame),
            Q_ARG(QByteArray, colors), Q_ARG(QString, window.title()));
    };
    if (!sample(window.size(), 0) || glass.backdropAt(QPointF(40,40)) != QColor(Qt::black)) return 8;
    const bool fractional = !qFuzzyCompare(window.devicePixelRatio(), qreal(qRound(window.devicePixelRatio())));
    if (!sample(window.size() + QSize(1,0), char(255))
        || glass.backdropAt(QPointF(40,40)) != QColor(Qt::white)) return 9;
    if (!sample(window.size() + QSize(2,0), 0)
        || glass.backdropAt(QPointF(40,40)) != QColor(fractional ? Qt::black : Qt::white)) return 11;
    const auto revision = glass.backdropRevision();
    if (!sample(window.size() + QSize(8,0), char(90)) || glass.backdropRevision() != revision) return 10;
    glass.setWindow(nullptr);
    std::cout << "CONTROL_GLASS_REGIONS_OK\n";
}
