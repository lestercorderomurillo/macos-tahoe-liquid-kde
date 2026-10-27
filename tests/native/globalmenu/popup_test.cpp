// SPDX-License-Identifier: GPL-3.0-or-later
#include "appmenuapplet.h"
#include "appmenumodel.h"
#include "dbusmenutypes_p.h"
#include <QApplication>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusVariant>
#include <QMenu>
#include <QProcess>
#include <QQuickItem>
#include <QQuickWindow>
#include <QSignalSpy>
#include <QStandardItemModel>
#include <QTest>

class DynamicExporter : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "com.canonical.dbusmenu")
    int openings = 0;
public Q_SLOTS:
    uint GetLayout(int parent, int, const QStringList&, DBusMenuLayoutItem& layout)
    {
        DBusMenuLayoutItem child {2, {{QStringLiteral("label"), QStringLiteral("Revision %1").arg(openings)}}, {}};
        DBusMenuLayoutItem file {
            1, {{QStringLiteral("label"), QStringLiteral("File")}, {QStringLiteral("children-display"), QStringLiteral("submenu")}}, {child}};
        layout = parent == 1 ? file : DBusMenuLayoutItem {0, {}, {file}};
        return openings + 1;
    }
    bool AboutToShow(int id)
    {
        if (id == 1)
            ++openings;
        return true;
    }
    int Openings() { return openings; }
    void Event(int, const QString&, const QDBusVariant&, uint) { }
Q_SIGNALS:
    void LayoutUpdated(uint revision, int parent);
};

class PopupTest : public QObject
{
    Q_OBJECT
private Q_SLOTS:
    void fileEditReopen()
    {
        QMenu root;
        auto* file = root.addMenu("File");
        auto* edit = root.addMenu("Edit");
        file->addAction("Open");
        edit->addAction("Copy");
        QStandardItemModel model(2, 1);
        model.setData(model.index(0, 0), QVariant::fromValue(file->menuAction()), AppMenuModel::ActionRole);
        model.setData(model.index(1, 0), QVariant::fromValue(edit->menuAction()), AppMenuModel::ActionRole);
        QQuickWindow window;
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        window.resize(400, 100);
        window.show();
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        connect(&applet, &AppMenuApplet::requestActivateIndex, &applet, [&](int index) { applet.trigger(&anchor, index); });
        applet.trigger(&anchor, 0);
        QCOMPARE(applet.currentIndex(), 0);
        auto* popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        QVERIFY(popup);
        QCOMPARE(popup->actions().first()->text(), QString("Open"));
        QTest::keyClick(popup, Qt::Key_Right);
        QCOMPARE(applet.currentIndex(), 1);
        QCOMPARE(popup->actions().first()->text(), QString("Copy"));
        popup->hide();
        QCOMPARE(applet.currentIndex(), -1);
        applet.trigger(&anchor, 0);
        QCOMPARE(applet.currentIndex(), 0);
        QCOMPARE(popup->actions().first()->text(), QString("Open"));
        popup->hide();
    }
    void notifiesSourceOnOpen()
    {
        QMenu root;
        auto* file = root.addMenu("File");
        file->addAction("Open");
        QSignalSpy opened(file, &QMenu::aboutToShow);
        QStandardItemModel model(1, 1);
        model.setData(model.index(0, 0), QVariant::fromValue(file->menuAction()), AppMenuModel::ActionRole);
        QQuickWindow window;
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        applet.trigger(&anchor, 0);
        const auto count = opened.count();
        if (auto* popup = QApplication::activePopupWidget())
            popup->hide();
        QCOMPARE(count, 1);
    }
    void disabledMenuDoesNotOpen()
    {
        QMenu root;
        auto* edit = root.addMenu("Edit");
        edit->addAction("Copy");
        edit->menuAction()->setEnabled(false);
        QStandardItemModel model(1, 1);
        model.setData(model.index(0, 0), QVariant::fromValue(edit->menuAction()), AppMenuModel::ActionRole);
        QQuickWindow window;
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        applet.trigger(&anchor, 0);
        const auto current = applet.currentIndex();
        if (auto* popup = QApplication::activePopupWidget())
            popup->hide();
        QCOMPARE(current, -1);
    }
    void refreshesDynamicDBusActionsOnEveryOpen()
    {
        QProcess exporter;
        exporter.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--exporter")});
        QVERIFY(exporter.waitForStarted());
        QVERIFY(exporter.waitForReadyRead());
        QDBusInterface remote("org.mttkde.PopupTest", "/Menu", "com.canonical.dbusmenu");
        auto openings = [&] { return remote.call("Openings").arguments().value(0).toInt(); };
        AppMenuModel model;
        model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus);
        model.updateApplicationMenu("org.mttkde.PopupTest", "/Menu");
        QTRY_COMPARE(model.rowCount(), 1);
        auto* action = model.index(0, 0).data(AppMenuModel::ActionRole).value<QAction*>();
        QVERIFY(action && action->menu());
        QTRY_COMPARE(action->menu()->actions().size(), 1);
        const int initial = openings();
        QQuickWindow window;
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        for (int i = 1; i <= 2; ++i) {
            applet.trigger(&anchor, 0);
            auto* popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
            QVERIFY(popup);
            QTRY_COMPARE(openings(), initial + i);
            QTRY_COMPARE(popup->actions().size(), 1);
            QTRY_COMPARE(popup->actions().first()->text(), QStringLiteral("Revision %1").arg(initial + i));
            popup->hide();
        }
        exporter.terminate();
        QVERIFY(exporter.waitForFinished());
    }
};
int main(int argc, char** argv)
{
    QApplication app(argc, argv);
    DBusMenuTypes_register();
    if (app.arguments().contains("--exporter")) {
        DynamicExporter exporter;
        auto bus = QDBusConnection::sessionBus();
        if (!bus.registerObject("/Menu", &exporter, QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals)
            || !bus.registerService("org.mttkde.PopupTest"))
            return 1;
        puts("ready");
        fflush(stdout);
        return app.exec();
    }
    PopupTest test;
    return QTest::qExec(&test, argc, argv);
}
#include "popup_test.moc"
