// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include <QGuiApplication>
#include <QVariantMap>
#include <QThread>
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
    const auto sample = [&](QSize size, char channel, QPoint offset = {}) {
        const QRect frame(window.position() + offset, size);
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
    // Five distinct column samples, repeated on three rows. A bright patch
    // covering 3/5 of a label may sustain an override but must not start one.
    QObject label;
    const QColor theme("#f4f4f4");
    const QPointF center(210, 125);
    const QSizeF radius(84, 20);
    const auto labelInk = [&](int brightColumns) {
        QByteArray colors(64 * 64 * 3, 0);
        for (int col = 0; col < brightColumns; ++col) {
            const int x = int((center.x() + (col - 2) * radius.width() / 2) * 64 / window.width());
            for (int y = 0; y < 64; ++y)
                colors.replace((y * 64 + x) * 3, 3, QByteArray(3, char(255)));
        }
        const QRect frame(window.position(), window.size());
        QMetaObject::invokeMethod(&glass, "updateBackdrop", Qt::DirectConnection,
            Q_ARG(int, int(app.applicationPid())), Q_ARG(QRect, frame), Q_ARG(QRect, frame),
            Q_ARG(QByteArray, colors), Q_ARG(QString, window.title()));
        return glass.animatedLabelForeground(&label, center, radius, theme, Qt::transparent);
    };
    if (labelInk(3) != theme || labelInk(4) != QColor(Qt::black)
        || labelInk(3) != QColor(Qt::black) || labelInk(2) != theme) return 12;

    const auto ink = [&] { return glass.animatedForegroundAt(&label, center, radius, theme, Qt::transparent); };
    // Anchored menus can move when search results change size. The next
    // sample still applies on the first paint, even if it reverses quickly.
    if (!sample(window.size(), 0) || ink() != QColor(Qt::white)
        || !sample(window.size(), char(255), QPoint(1, 0)) || ink() != QColor(Qt::black)
        || !sample(window.size(), 0, QPoint(2, 0)) || ink() != QColor(Qt::white)) return 13;

    glass.windowMoveStarted();
    if (!sample(window.size(), char(255), QPoint(3, 0)) || ink() != QColor(Qt::white)) return 14;
    QThread::msleep(320);
    if (ink() != QColor(Qt::black)) return 15;
    if (!sample(window.size(), 0, QPoint(3, 0)) || ink() != QColor(Qt::white)) return 16;
    glass.setWindow(nullptr);
    std::cout << "CONTROL_GLASS_REGIONS_OK\n";
}
