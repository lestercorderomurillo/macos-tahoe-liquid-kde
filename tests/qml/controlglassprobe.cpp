// SPDX-License-Identifier: GPL-3.0-or-later
#include "controlglass.h"
#include "glassink.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QPropertyAnimation>
#include <QTextOption>
#include <QQuickWindow>
#include <memory>
#include <QUrl>
#include <QVariantMap>
#include <QThread>
#include <limits>
#include <iostream>

// Compare the background-only sampler against the painted window. The two
// glyph centers lie inside one 64-column cell on opposite sides of the SVG edge.
static bool checkPaintedMaterial()
{
    QQmlEngine engine;
    QQmlComponent component(&engine);
    component.setData(R"(import QtQuick
        Image { asynchronous: false; cache: false; width: 1024; height: 32 })", QUrl());
    std::unique_ptr<QObject> object(component.create());
    auto *item = qobject_cast<QQuickItem *>(object.get());
    if (!item) { qWarning() << component.errors(); return false; }
    const QByteArray svg = R"SVG(<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="32">
        <defs><linearGradient id="ink"><stop stop-color="red" stop-opacity="0.2"/>
        <stop offset="1" stop-color="red" stop-opacity="0.8"/></linearGradient></defs>
        <path fill="black" d="M0 0h8v32H0z"/><path fill="white" d="M8 0h24v32H8z"/>
        <rect x="40" width="120" height="32" fill="url(#ink)"/></svg>)SVG";
    item->setProperty("source", QUrl("data:image/svg+xml;base64," + svg.toBase64()));
    QQuickWindow window;
    window.resize(1024, 32);
    window.setColor(QColor("#2468ad"));
    item->setParentItem(window.contentItem());
    window.show();
    MaterialSample material;
    material.setSource(item);
    QElapsedTimer timer;
    timer.start();
    while (material.at({4, 12}) != QColor(Qt::black) && timer.elapsed() < 3000) {
        QCoreApplication::processEvents();
        QThread::msleep(4);
    }
    const QImage rendered = window.grabWindow();
    if (rendered.isNull()) return false;
    const qreal dpr = window.devicePixelRatio();
    auto close = [](QColor a, QColor b) {
        return a.isValid() && b.isValid() && std::abs(a.red()-b.red()) <= 2
            && std::abs(a.green()-b.green()) <= 2 && std::abs(a.blue()-b.blue()) <= 2;
    };
    QFont font;
    font.setPixelSize(12);
    const QString joined = QStringLiteral("e\u0301");
    if (MaterialSample::textRuns(joined, font, 100, 0, Qt::AlignLeft, true).size() != 1) return false;
    const QString wrapped = QStringLiteral("Open coastal field notes");
    const auto lines = MaterialSample::textRuns(wrapped, font, 50, QTextOption::WordWrap, Qt::AlignLeft, false);
    QString recovered;
    qreal bottom = -1.;
    for (const auto &line : lines) {
        const auto value = line.toMap();
        const auto rect = value.value("bounds").toRectF();
        if (rect.top() < bottom - .01) return false;
        bottom = rect.bottom();
        recovered += value.value("text").toString();
    }
    if (lines.size() < 2 || recovered != wrapped) return false;
    const auto glyphs = MaterialSample::textRuns(QStringLiteral("ii"), font, 100, 0, Qt::AlignLeft, true);
    if (glyphs.size() != 2) return false;
    auto center = [&](int i) { return glyphs[i].toMap().value("bounds").toRectF().center(); };
    const qreal xOffset = 8 - (center(0).x() + center(1).x())/2;
    const QPointF first = center(0) + QPointF(xOffset, 0);
    const QPointF second = center(1) + QPointF(xOffset, 0);
    if (int(first.x()/16) != int(second.x()/16) || material.at(first) != QColor(Qt::black)
        || material.at(second) != QColor(Qt::white)) return false;
    for (const auto point : {first, second, QPointF(55,16), QPointF(145,16), QPointF(220,16)}) {
        const auto layer = material.at(point);
        const auto observed = rendered.pixelColor(qFloor(point.x()*dpr), qFloor(point.y()*dpr));
        if (!close(GlassInk::composite(window.color(), layer), observed)) return false;
    }
    if (material.at({220,16}).alpha() != 0 || material.at({55,16}).alpha() <= 0
        || material.at({55,16}).alpha() >= material.at({145,16}).alpha() || material.at({145,16}).alpha() >= 255) return false;
    PopupBackdrop popup;
    window.setTitle(QStringLiteral("mttkde-apps"));
    popup.setWindow(&window);
    const QRect frame = window.geometry();
    QByteArray backdrop(64 * 64 * 3, 0);
    for (int i = 0; i < backdrop.size(); i += 3) {
        backdrop[i] = char(window.color().red());
        backdrop[i + 1] = char(window.color().green());
        backdrop[i + 2] = char(window.color().blue());
    }
    if (!QMetaObject::invokeMethod(&popup, "updateBackdrop", Qt::DirectConnection,
            Q_ARG(int, int(QCoreApplication::applicationPid())), Q_ARG(QRect, frame),
            Q_ARG(QRect, frame), Q_ARG(QByteArray, backdrop), Q_ARG(QString, window.title()))) return false;
    const QColor base(Qt::black);
    const QJsonObject profile{{"scope", "letter"}, {"sampleCount", 1}, {"correction", "flip"}};
    const auto inkAt = [&](QPointF point) {
        return popup.surfaceForeground(item, QRectF(point-QPointF(.25,.25), QSizeF(.5,.5)),
                                       base, base, Qt::transparent, profile, &material, Qt::transparent);
    };
    if (inkAt(first) != QColor(Qt::white) || inkAt(second) != base) return false;
    // The same two labels can take one correction per tile, independent of
    // their positions within that tile and of the neighboring tile.
    const QJsonObject tileProfile{{"scope", "bubble"}, {"sampleCount", 15}, {"correction", "flip"}};
    QObject otherLabel;
    const auto tileInk = [&](QObject *label, QRectF tile) {
        return popup.surfaceForeground(label, tile, base, base, Qt::transparent, tileProfile, &material, Qt::transparent);
    };
    const QRectF darkTile(0,0,7,32), lightTile(10,0,20,32);
    if (tileInk(item, darkTile) != QColor(Qt::white) || tileInk(&otherLabel, darkTile) != QColor(Qt::white)
        || tileInk(item, lightTile) != base || tileInk(&otherLabel, darkTile) != QColor(Qt::white)) return false;
    // Animate a real Qt Quick item over alternating threshold-adjacent cells.
    // The last four cells are clearly light enough to restore the original ink.
    for (int y = 0; y < 64; ++y) for (int x = 0; x < 64; ++x) {
        const int value = x >= 60 ? 100 : 77 + x % 2;
        std::fill_n(backdrop.data() + 3 * (y * 64 + x), 3, char(value));
    }
    if (!QMetaObject::invokeMethod(&popup, "updateBackdrop", Qt::DirectConnection,
            Q_ARG(int, int(QCoreApplication::applicationPid())), Q_ARG(QRect, frame),
            Q_ARG(QRect, frame), Q_ARG(QByteArray, backdrop), Q_ARG(QString, window.title()))) return false;
    QQuickItem moving(window.contentItem());
    moving.setSize(QSizeF(1,1));
    QPropertyAnimation motion(&moving, "x");
    motion.setDuration(450);
    motion.setStartValue(0.);
    motion.setEndValue(992.);
    int decisions = 0;
    bool stable = true;
    const auto observe = [&] {
        ++decisions;
        const auto r = moving.mapRectToScene(moving.boundingRect());
        const auto ink = popup.surfaceForeground(&moving, r, base, base, Qt::transparent, profile,
                                                 nullptr, Qt::transparent, 0);
        stable &= ink == QColor(r.center().x() < 960 ? Qt::white : Qt::black);
    };
    observe();
    QObject::connect(&moving, &QQuickItem::xChanged, &moving, observe);
    QEventLoop animation;
    QObject::connect(&motion, &QPropertyAnimation::finished, &animation, &QEventLoop::quit);
    motion.start();
    animation.exec();
    if (!stable || decisions < 4) return false;
    std::cout << "Animated Qt Quick item: " << decisions << " observed positions; stable on gray 77/78, returned to black on gray 100.\n";
    const auto shaderPath = qEnvironmentVariable("CONTRAST_SHADER_FRAME");
    if (!shaderPath.isEmpty()) {
        const QImage gpu(shaderPath);
        if (gpu.size() != QSize(192,128)) return false;
        item->setSize(gpu.size());
        window.resize(gpu.size());
        item->setProperty("source", QUrl::fromLocalFile(shaderPath));
        material.invalidate();
        timer.restart();
        while (timer.elapsed() < 3000 && !close(material.at({96,12}), gpu.pixelColor(96,12))) {
            QCoreApplication::processEvents();
            QThread::msleep(4);
        }
        const auto top = material.at({96,12}), bottom = material.at({96,115});
        if (!close(top, gpu.pixelColor(96,12)) || !close(bottom, gpu.pixelColor(96,115))
            || top.red()+40 >= bottom.red()) return false;
        std::cout << "Captured glass shader output: backing gray 160, material samples "
                  << top.red() << " and " << bottom.red() << "\n";
    }
    std::cout << "SVG, gradient and transparent pixels matched the rendered window at " << dpr
              << "x; glyph centers at physical x=" << qFloor(first.x()*dpr) << " and "
              << qFloor(second.x()*dpr) << " resolved black and white inside one grid cell.\n";
    return true;
}

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    if (!checkPaintedMaterial()) return 35;
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
                || tone.alpha() != base.alpha() || std::abs(tone.red() - base.red()) > 112) return 27;
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
    GlassInk::Samples mostlyDark, mostlyLight;
    for (int i = 0; i < 15; ++i) {
        mostlyDark.add(i == 0 ? Qt::white : Qt::black);
        mostlyLight.add(i == 0 ? Qt::black : Qt::white);
    }
    if (mostlyDark.tone(theme) == mostlyLight.tone(theme)) return 32;
    GlassInk::Samples black;
    black.add(Qt::black);
    if (black.tone(Qt::black, {GlassInk::Correction::Flip}) != QColor(Qt::white)) return 33;
    // At the default 33 L* target, translucent black needs 105 channel steps
    // on a gray-10 surface. The previous limit stops short of the target.
    GlassInk::Samples nearBlack;
    const QColor dark(10,10,10);
    const QColor translucentBlack(0,0,0,200);
    nearBlack.add(dark);
    const auto limited = nearBlack.tone(translucentBlack, {GlassInk::Correction::Shift, .33, 102});
    const auto extended = nearBlack.tone(translucentBlack);
    const auto separation = [&](QColor ink) {
        return std::abs(GlassInk::lightness(GlassInk::composite(dark, ink)) - GlassInk::lightness(dark));
    };
    if (limited.red() != 102 || extended.red() != 105 || separation(limited) >= .33 || separation(extended) < .33) return 37;
    GlassInk::Samples capped;
    const QColor mid(135,135,135);
    capped.add(mid);
    if (capped.tone(mid, {GlassInk::Correction::Shift, .9, 102}).red() != 237
        || capped.tone(mid, {GlassInk::Correction::Shift, .9, 112}).red() != 247) return 36;
    GlassInk::FlipHistory history;
    const GlassInk::CorrectionSettings flip{GlassInk::Correction::Flip};
    const auto movingInk = [&](int gray, int glyph) {
        GlassInk::Samples frame;
        frame.add(QColor(gray, gray, gray));
        return history.tone(frame, Qt::black, flip, &label, glyph);
    };
    if (movingInk(77, 0) != QColor(Qt::white) || movingInk(78, 1) != QColor(Qt::black)) return 38;
    for (int i = 0; i < 20; ++i) if (movingInk(77 + i % 2, 0) != QColor(Qt::white)) return 38;
    if (movingInk(100, 0) != QColor(Qt::black) || movingInk(78, 0) != QColor(Qt::black)) return 38;
    GlassInk::Samples gray;
    gray.add(QColor(118, 118, 118));
    if (gray.tone(Qt::white, {GlassInk::Correction::Shift, .9, 112})
        != QColor(Qt::white)) return 34;
    const auto margin = GlassInk::sample(GlassInk::label, {}, QSizeF(10, 10),
        [](QPointF point) { return point.isNull() ? QColor(Qt::white) : QColor(); });
    if (margin.tone(theme) != overWhite) return 26;
    glass.setWindow(nullptr);
    std::cout << "CONTROL_GLASS_REGIONS_OK\n";
}
