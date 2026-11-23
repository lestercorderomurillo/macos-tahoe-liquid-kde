// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include "glassink.h"
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
    QObject label;
    const QColor theme("#f4f4f4");
    auto material = rect(0, 0, window.width(), window.height(), 0);
    material.insert("fill", QColor(Qt::transparent));
    glass.setSurfaces({material});
    const QPointF center(210, 125);
    const QSizeF radius(84, 20);
    const auto localTone = [](QColor surface, QColor base) {
        GlassInk::Samples local;
        local.add(surface);
        return local.tone(base);
    };
    const auto overBlack = localTone(Qt::black, theme);
    const auto overWhite = localTone(Qt::white, theme);

    // Different labels keep readable base colors on both sides of the same popup.
    QByteArray split(8 * 8 * 3, 0);
    for (int y = 0; y < 8; ++y) std::fill_n(split.data() + (y * 8 + 6) * 3, 6, char(255));
    const QRect frame(window.position(), window.size());
    QMetaObject::invokeMethod(&glass, "updateBackdrop", Qt::DirectConnection,
        Q_ARG(int, int(app.applicationPid())), Q_ARG(QRect, frame), Q_ARG(QRect, frame),
        Q_ARG(QByteArray, split), Q_ARG(QString, window.title()));
    const QColor lightOnDark = glass.animatedLabelForeground(&label, {30, 75}, {}, theme, Qt::transparent);
    const QColor darkOnLight = glass.animatedLabelForeground(&label, {390, 75}, {}, Qt::black, Qt::transparent);
    if (lightOnDark != theme || darkOnLight != QColor(Qt::black)
        || glass.groupForeground(&label, theme, {Qt::white}) != overWhite) return 12;
    // Two labels using exactly the same theme role can need different ink.
    QObject secondLabel;
    if (glass.animatedLabelForeground(&secondLabel, {390, 75}, {}, theme, Qt::transparent) != overWhite
        || overWhite == lightOnDark) return 29;
    if (glass.animatedLabelForeground(&label, {390, 75}, {}, theme, Qt::black) != theme) return 19;

    const auto ink = [&] { return glass.animatedForegroundAt(&label, center, radius, theme, Qt::transparent); };
    // Anchored menus can move when search results change size. The next
    // sample still applies on the first paint, even if it reverses quickly.
    if (!sample(window.size(), 0) || ink() != overBlack
        || !sample(window.size(), char(255), QPoint(1, 0)) || ink() != overWhite
        || !sample(window.size(), 0, QPoint(2, 0)) || ink() != overBlack) return 13;

    const auto markMoving = [&](QPoint offset) {
        return QMetaObject::invokeMethod(&glass, "movingControlSample", Qt::DirectConnection,
            Q_ARG(int, int(app.applicationPid())), Q_ARG(QRect, QRect(window.position() + offset, window.size())),
            Q_ARG(QString, window.title()));
    };
    if (!markMoving(QPoint(2, 0)) || !sample(window.size(), char(255), QPoint(2, 0)) || ink() != overWhite) return 20;
    if (!sample(window.size(), 0, QPoint(2, 0)) || ink() != overBlack || !markMoving(QPoint(3, 0))) return 21;
    if (!sample(window.size(), char(255), QPoint(3, 0)) || ink() != overBlack) return 14;
    QThread::msleep(320);
    if (ink() != overWhite) return 15;
    if (!sample(window.size(), 0, QPoint(3, 0)) || ink() != overBlack) return 16;
    if (!markMoving(QPoint(4, 0)) || !sample(window.size(), char(255), QPoint(4, 0)) || ink() != overBlack) return 22;
    // A stationary update immediately following the last drag frame must snap.
    if (!sample(window.size(), char(160), QPoint(5, 0)) || ink() != glass.foregroundAt(center, radius, theme, Qt::transparent)) return 23;
    for (const QColor base : {QColor(Qt::black), QColor(Qt::white), QColor("#232323"), QColor("#f1f1f1")}) {
        if (localTone(QColor(), base) != base) return 18;
        for (int gray = 0; gray <= 255; ++gray) {
            const QColor backdrop(gray, gray, gray);
            const QColor tone = localTone(backdrop, base);
            const double surface = GlassInk::lightness(backdrop);
            const double before = std::abs(GlassInk::lightness(base) - surface);
            const double after = std::abs(GlassInk::lightness(tone) - surface);
            if ((before >= .33 && tone != base) || after < before
                || GlassInk::familyOf(tone) != GlassInk::familyOf(base)
                || tone.alpha() != base.alpha() || std::abs(tone.red() - base.red()) > 102) return 27;
        }
    }
    if (localTone(Qt::black, Qt::black).red() != 78 || localTone(Qt::white, Qt::white).red() != 163
        || overWhite.red() >= theme.red() || overBlack != theme) return 28;
    const QColor appsBase("#242424");
    const QColor darkBackdrop("#070707");
    const QColor appsInk = localTone(darkBackdrop, appsBase);
    if (GlassInk::lightness(appsInk) - GlassInk::lightness(darkBackdrop) < .33
        || localTone(Qt::white, appsBase) != appsBase) return 31;
    const QColor translucent(36, 36, 36, 128);
    const QColor corrected = localTone(Qt::black, translucent);
    if (corrected.alpha() != translucent.alpha() || corrected == translucent
        || GlassInk::lightness(GlassInk::composite(Qt::black, corrected))
            <= GlassInk::lightness(GlassInk::composite(Qt::black, translucent))) return 30;
    const QRectF clipped(center.x(), 0, radius.width(), window.height());
    const auto visibleSamples = glass.categorySamples(center, radius, clipped, Qt::transparent);
    if (visibleSamples.size() != 2 || visibleSamples.front() != QColor(160, 160, 160)) return 24;
    const auto centered = GlassInk::sample(GlassInk::control, {}, QSizeF(10, 10),
        [](QPointF point) { return point.isNull() ? QColor(Qt::white) : QColor(Qt::black); });
    GlassInk::Samples weighted;
    weighted.add(Qt::white, .65); weighted.add(Qt::black, .35);
    if (centered.tone(theme) != weighted.tone(theme)) return 25;
    const auto margin = GlassInk::sample(GlassInk::label, {}, QSizeF(10, 10),
        [](QPointF point) { return point.isNull() ? QColor(Qt::white) : QColor(); });
    if (margin.tone(theme) != overWhite) return 26;
    glass.setWindow(nullptr);
    std::cout << "CONTROL_GLASS_REGIONS_OK\n";
}
