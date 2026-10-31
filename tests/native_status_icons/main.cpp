// SPDX-License-Identifier: GPL-3.0-or-later
#include <QApplication>
#include <QDir>
#include <QImage>
#include <QPalette>
#include <KIconLoader>
#include <KIconTheme>
#include <QIcon>
#include <QStandardPaths>
#include <iostream>

int main(int argc, char **argv)
{
    KIconTheme::initTheme();
    QApplication app(argc, argv);
    if (argc != 3) return 2;
    KIconTheme::forceThemeForTests(QString::fromLocal8Bit(argv[1]));
    QIcon::setThemeSearchPaths({QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) + "/icons"});
    KIconLoader loader;
    const QString output = QString::fromLocal8Bit(argv[2]);
    QDir().mkpath(output);
    int renders = 0;
    for (const auto *mode : {"light", "dark", "light-again"}) {
        const bool dark = QString::fromLatin1(mode) == "dark";
        QPalette palette;
        for (auto role : {QPalette::WindowText, QPalette::Text, QPalette::ButtonText})
            palette.setColor(role, QColor(dark ? "#eeeeee" : "#222222"));
        palette.setColor(QPalette::Window, QColor(dark ? "#222222" : "#eeeeee"));
        loader.setCustomPalette(palette);
        app.setPalette(palette);
        QIcon::setThemeName(QString::fromLocal8Bit(argv[1]));
        for (const auto *name : {"battery", "camera", "camera-web", "preferences-desktop-display-nightcolor",
                                 "kdeconnect", "kdeconnect-tray", "audio-volume-high", "network-wireless-signal-excellent",
                                 "bluetooth-active", "brightness-high", "redshift-status-on"}) {
            for (int size : {16, 22, 24, 32, 48, 64}) {
                QString path;
                const auto image = loader.loadScaledIcon(QString::fromLatin1(name), KIconLoader::Panel,
                    1.0, size, KIconLoader::DefaultState, {}, &path, true).toImage();
                int visible = 0, wrong = 0;
                for (int y = 0; y < image.height(); ++y) {
                    for (int x = 0; x < image.width(); ++x) {
                        const auto color = image.pixelColor(x, y);
                        if (color.alpha() < 100) continue;
                        ++visible;
                        if (color.hsvSaturation() > 30 || (dark ? color.value() < 180 : color.value() > 80)) ++wrong;
                    }
                }
                if (visible < 5 || wrong || !path.contains("MacTahoeLiquidKde-Icons")) {
                    std::cerr << mode << " interface " << name << " size=" << size
                              << " wrong=" << wrong << " path=" << path.toStdString() << std::endl;
                    return 1;
                }
                if (QIcon::fromTheme(QString::fromLatin1(name)).pixmap(size).isNull()) {
                    std::cerr << "QIcon missing " << name << " theme=" << QIcon::themeName().toStdString() << std::endl; return 1;
                }
                if (size == 48) image.save(output + '/' + mode + '-' + name + ".png");
                ++renders;
            }
        }
        for (int level = 0; level <= 100; level += 10) {
            for (const auto *suffix : {"", "-charging", "-symbolic", "-charging-symbolic"}) {
                const QString name = QString("battery-%1%2").arg(level, 3, 10, QChar('0')).arg(suffix);
                for (int size : {16, 22, 24, 32}) {
                    for (qreal scale : {1.0, 1.25, 1.5, 2.0}) {
                        QString path;
                        const auto image = loader.loadScaledIcon(name, KIconLoader::Panel, scale, size,
                            KIconLoader::DefaultState, {}, &path, true).toImage();
                        int visible = 0, neutral = 0, wrong = 0;
                        for (int y = 0; y < image.height(); ++y) {
                            for (int x = 0; x < image.width(); ++x) {
                                const auto color = image.pixelColor(x, y);
                                if (color.alpha() < 100) continue;
                                ++visible;
                                if (color.hsvSaturation() > 30) continue;
                                ++neutral;
                                if (dark ? color.value() < 180 : color.value() > 80) ++wrong;
                            }
                        }
                        if (visible < 5 || wrong || !path.contains("MacTahoeLiquidKde-Icons")) {
                            std::cerr << mode << " " << name.toStdString() << " " << size << "@" << scale
                                      << " neutral=" << neutral << " wrong=" << wrong
                                      << " path=" << path.toStdString() << std::endl;
                            return 1;
                        }
                        if (size == 24 && scale == 2.0)
                            image.save(output + '/' + mode + '-' + name + ".png");
                        ++renders;
                    }
                }
            }
        }
    }
    std::cout << renders << " status icon renders passed, including light/dark/light" << std::endl;
}
