// SPDX-License-Identifier: GPL-3.0-only
// Run in a disposable Plasma session with its real platform and Kvantum plugins.
#include <systemmenustyle.h>
#include <QFile>
#include <QSaveFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <QLabel>

static QJsonObject pixel(QMenu &menu, const QString &path) {
    QStyleOption option;
    option.initFrom(&menu);
    option.rect = QRect(0, 0, 300, 200);
    QImage image(option.rect.size(), QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    menu.style()->drawPrimitive(QStyle::PE_PanelMenu, &option, &painter, &menu);
    painter.end();
    image.save(path);
    const QColor color = image.pixelColor(150, 100);
    return {{"red", color.red()}, {"green", color.green()}, {"blue", color.blue()},
            {"alpha", color.alpha()}, {"text", menu.palette().color(QPalette::WindowText).lightness()}};
}
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    if (argc != 2) return 2;
    const QString output = QString::fromLocal8Bit(argv[1]);
    QLabel window(QStringLiteral("Appearance synchronization probe"));
    window.resize(480, 160);
    window.show();
    QMenu system, ordinary;
    system.addAction(QStringLiteral("About This Computer"));
    ordinary.addAction(QStringLiteral("Ordinary application menu"));
    system.setStyle(new SystemMenuStyle(&system));
    // Keep both widgets and the application alive for every transition.
    system.ensurePolished(); ordinary.ensurePolished();
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, [&] {
        const QJsonObject result {
            {"style", app.style()->objectName()},
            {"background", app.palette().color(QPalette::Window).lightness()},
            {"foreground", app.palette().color(QPalette::WindowText).lightness()},
            {"system", pixel(system, output + "/system.png")},
            {"ordinary", pixel(ordinary, output + "/ordinary.png")},
        };
        QSaveFile file(output + "/probe.json");
        if (file.open(QIODevice::WriteOnly)) {
            file.write(QJsonDocument(result).toJson()); file.commit();
        }
    });
    timer.start(250);
    return app.exec();
}
