// SPDX-License-Identifier: GPL-3.0-or-later
#include <QApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <KIconLoader>
#include <KIconTheme>
#include <iostream>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QJsonObject themes;
    for (int i = 1; i < argc; ++i) {
        const QString theme = QString::fromLocal8Bit(argv[i]);
        KIconTheme::forceThemeForTests(theme);
        KIconLoader loader;
        QJsonObject icons;
        for (const auto *name : {"computer", "preferences-system", "software-store-symbolic",
                                 "systemsettings", "org.kde.discover"}) {
            QJsonArray hashes;
            for (int size : {16, 22, 32}) {
                for (qreal scale : {1.0, 2.0}) {
                    QFile file(loader.iconPath(QString::fromLatin1(name), -size, true, scale));
                    if (!file.open(QIODevice::ReadOnly)) {
                        std::cerr << "Missing icon: " << name << std::endl;
                        return 1;
                    }
                    hashes.append(QString::fromLatin1(QCryptographicHash::hash(
                        file.readAll(), QCryptographicHash::Sha256).toHex()));
                }
            }
            icons.insert(QString::fromLatin1(name), hashes);
        }
        themes.insert(theme, icons);
    }
    std::cout << QJsonDocument(themes).toJson(QJsonDocument::Compact).constData();
}
