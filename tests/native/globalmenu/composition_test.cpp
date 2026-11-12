// SPDX-License-Identifier: GPL-3.0-or-later
#include <Plasma/Corona>
#include <Plasma/Containment>
#include <PlasmaQuick/AppletQuickItem>
#include <QApplication>
#include <QMenu>
#include <QQuickWindow>
#include <QTest>
#include <QQmlEngine>
#include <QQmlProperty>
#include <QStandardItemModel>
#include <tasksmodel.h>
#include <abstracttasksmodel.h>
#include <KConfigGroup>
#include <KConfigLoader>
#include <KConfigPropertyMap>
#include <KPackage/PackageLoader>
#include <KPackage/Package>

class TestCorona : public Plasma::Corona
{
public:
    // Plasma SDKs use either signed or unsigned screen IDs.
    QRect screenGeometry(int) const { return {0, 0, 1280, 720}; }
    QRect screenGeometry(uint) const { return {0, 0, 1280, 720}; }
};

class CompositionTest : public QObject
{
    Q_OBJECT
private Q_SLOTS:
    void remainsAMenuApplet()
    {
        TestCorona corona;
        auto *panel = corona.createContainment(QString());
        QVERIFY(panel);
        panel->setFormFactor(Plasma::Types::Horizontal);
        panel->setLocation(Plasma::Types::TopEdge);
        auto *bar = panel->createApplet(QStringLiteral("org.kde.mac.tahoe.liquid.globalmenu"));
        QVERIFY(bar);
        QVERIFY2(!bar->failedToLaunch(), qPrintable(bar->launchErrorMessage()));
        QVERIFY(!qobject_cast<Plasma::Containment *>(bar));
        QQuickWindow window;
        window.resize(1280, 32);
        auto *item = PlasmaQuick::AppletQuickItem::itemForApplet(bar);
        QVERIFY(item);
        item->setParentItem(window.contentItem());
        item->setSize({1280, 32});
        window.show();
        QTRY_VERIFY_WITH_TIMEOUT(item->fullRepresentationItem(), 10000);
        auto *model = bar->property("model").value<QObject *>();
        QVERIFY(model);
        auto *tasks = model->findChild<TaskManager::TasksModel *>();
        QVERIFY(tasks);
        QStandardItemModel source(1, 1);
        const auto task = source.index(0, 0);
        using Roles = TaskManager::AbstractTasksModel;
        source.setData(task, QVariantList{101}, Roles::WinIdList);
        source.setData(task, true, Roles::IsWindow);
        source.setData(task, true, Roles::IsActive);
        source.setData(task, QStringLiteral("Menu Test Application"), Roles::AppName);
        QTRY_VERIFY(tasks->sourceModel());
        tasks->setSourceModel(&source);
        Q_EMIT tasks->activeTaskChanged();
        QTRY_VERIFY(model->property("menuAvailable").toBool());
        auto *representation = item->fullRepresentationItem();
        QQmlProperty minimumWidth(representation, QStringLiteral("Layout.minimumWidth"), qmlContext(representation));
        QVERIFY(minimumWidth.isValid());
        QTRY_VERIFY(minimumWidth.read().toReal() > 250);
        for (const char* method : {"triggerSystemMenu", "triggerWindowMenu"}) {
            QVERIFY(QMetaObject::invokeMethod(bar, method, Q_ARG(QQuickItem*, representation)));
            QTRY_COMPARE(bar->status(), Plasma::Types::NeedsAttentionStatus);
            auto* popup = QApplication::activePopupWidget();
            QVERIFY(popup);
            popup->hide();
            QTRY_COMPARE(bar->status(), Plasma::Types::ActiveStatus);
        }
        QVERIFY(QMetaObject::invokeMethod(bar, "triggerWindowMenu", Q_ARG(QQuickItem*, representation)));
        auto *popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        QVERIFY(popup);
        auto *about = popup->actions().first();
        QTest::mouseClick(popup, Qt::LeftButton, Qt::NoModifier, popup->actionGeometry(about).center());
        QWindow *aboutWindow = nullptr;
        QTRY_VERIFY([&] {
            for (auto *candidate : QGuiApplication::topLevelWindows())
                if (candidate->objectName() == QLatin1String("applicationAboutWindow")) aboutWindow = candidate;
            return aboutWindow && aboutWindow->isVisible();
        }());
        QCOMPARE(aboutWindow->title(), QStringLiteral("About Menu Test Application"));
        QCOMPARE(aboutWindow->property("applicationInfo").toMap().value("name").toString(), QStringLiteral("Menu Test Application"));
        aboutWindow->close();
        QCOMPARE(panel->applets().size(), 1);
        QVERIFY(!bar->configuration()->contains(QStringLiteral("integratedBar")));
    }
};
QTEST_MAIN(CompositionTest)
#include "composition_test.moc"
