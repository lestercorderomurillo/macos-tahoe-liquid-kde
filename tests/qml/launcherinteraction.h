// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QCursor>
#include <QIcon>
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTest>
#include <QVariantMap>

// Test-only input to the actual popup window and inspection of rendered items.
class LauncherInteraction : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    static QQuickWindow *menuWindow() {
        for (auto *window : QGuiApplication::topLevelWindows())
            if (window->isVisible() && window->objectName() == "launcherOptionsMenu")
                return qobject_cast<QQuickWindow *>(window);
        return nullptr;
    }
    static void collectRows(QQuickItem *item, QMap<int, QVariantMap> &rows) {
        if (item->objectName() == "launcherOption") {
            auto *action = item->property("modelData").value<QObject *>();
            if (action) rows.insert(item->property("index").toInt(), {
                {"text", action->property("text")},
                {"separator", action->property("section").toBool() || action->property("separator").toBool()},
                {"checked", action->property("checked")},
                {"rect", QRectF(item->mapToScene(QPointF()), QSizeF(item->width(), item->height()))}});
        }
        for (auto *child : item->childItems()) collectRows(child, rows);
    }
public:
    using QObject::QObject;
    Q_INVOKABLE void setIconTheme(const QString &directory, const QString &name) {
        QIcon::setThemeSearchPaths({directory});
        QIcon::setThemeName(name);
    }
    Q_INVOKABLE QColor pixel(QQuickItem *item) {
        const auto position = item->mapToScene(QPointF(item->width()/2, item->height()/2));
        return item->window()->grabWindow().pixelColor((position * item->window()->devicePixelRatio()).toPoint());
    }
    Q_INVOKABLE QVariantMap menuState() const {
        auto *menu = menuWindow();
        if (!menu) return {};
        QMap<int, QVariantMap> rows;
        collectRows(menu->contentItem(), rows);
        QVariantList actions;
        for (const auto &row : rows) actions.append(row);
        const auto selected = menu->property("selectedIndex").toInt();
        return {{"rect", menu->geometry()}, {"actions", actions},
            {"active", rows.value(selected).value("text", QString())}};
    }
    Q_INVOKABLE void click(QQuickItem *item) {
        const auto pos = item->mapToScene(QPointF(item->width()/2, item->height()/2)).toPoint();
        QCursor::setPos(item->window()->mapToGlobal(pos));
        QTest::mouseClick(item->window(), Qt::LeftButton, Qt::NoModifier, pos);
        QTest::qWait(30);
    }
    Q_INVOKABLE void pointer(int x, int y) {
        QCursor::setPos(x, y);
        if (auto *menu = menuWindow())
            QTest::mouseMove(menu, menu->mapFromGlobal(QPoint(x, y)));
        QTest::qWait(30);
    }
    Q_INVOKABLE void key(int key) {
        if (auto *menu = menuWindow()) QTest::keyClick(menu, static_cast<Qt::Key>(key));
    }
    Q_INVOKABLE void choose(int index) {
        if (auto *menu = menuWindow()) {
            QMap<int, QVariantMap> rows;
            collectRows(menu->contentItem(), rows);
            const auto pos = rows.value(index).value("rect").toRectF().center().toPoint();
            QTest::mouseMove(menu, pos);
            QTest::mouseClick(menu, Qt::LeftButton, Qt::NoModifier, pos);
            QTest::qWait(30);
        }
    }
    Q_INVOKABLE QSize bufferSize(QQuickWindow *window) {
        return window->grabWindow().size() / window->devicePixelRatio();
    }
};
