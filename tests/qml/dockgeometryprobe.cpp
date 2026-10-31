// SPDX-License-Identifier: GPL-2.0-or-later
#include <QGuiApplication>
#include <QIcon>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickView>
#include <QTimer>
#include <QDebug>
#include <memory>

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    if (argc != 2) {
        return 2;
    }
    const QString iconTheme = qEnvironmentVariable("DOCK_ICON_THEME");
    if (!iconTheme.isEmpty()) {
        QIcon::setThemeName(iconTheme);
    }
    QQuickView view;
    QObject::connect(view.engine(), &QQmlEngine::exit, &app, [&view, &app](int code) {
        const QString capture = qEnvironmentVariable("DOCK_CAPTURE_PATH");
        if (!capture.isEmpty() && !view.grabWindow().save(capture)) {
            code = 4;
        }
        app.exit(code);
    });
    const QUrl url = QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]));
    QQmlComponent component(view.engine(), url);
    std::unique_ptr<QObject> root(component.create());
    if (!root) {
        qCritical() << component.errors();
        return 1;
    }
    view.setContent(url, &component, root.release());
    view.show();
    qInfo() << "DOCK_DPR:" << view.devicePixelRatio();
    QTimer::singleShot(30000, &app, [&app] { app.exit(3); });
    return app.exec();
}
