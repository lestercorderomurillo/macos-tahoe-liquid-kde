// SPDX-License-Identifier: GPL-3.0-or-later
#include <Plasma/Corona>
#include <Plasma/Containment>
#include <PlasmaQuick/AppletQuickItem>
#include <QApplication>
#include <QQuickWindow>
#include <QTest>
#include <QQmlEngine>
#include <QQmlProperty>
#include <QStandardItemModel>
#include <tasksmodel.h>
#include <abstracttasksmodel.h>
#include <KConfigGroup>
#include <KConfigLoader>
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
    void containsOneTrayAndClock()
    {
        TestCorona corona;
        corona.setKPackage(KPackage::PackageLoader::self()->loadPackage(QStringLiteral("Plasma/Shell"), QStringLiteral("org.kde.plasma.desktop")));
        QVERIFY2(corona.kPackage().isValid(), "The plasma-desktop shell package is required for native accessory representations");
        auto* panel = corona.createContainment(QString());
        QVERIFY(panel);
        auto* bar = qobject_cast<Plasma::Containment*>(panel->createApplet(QStringLiteral("org.kde.mac.tahoe.liquid.globalmenu")));
        QVERIFY(bar);
        QVERIFY2(bar->pluginMetaData().isValid(), qPrintable(bar->launchErrorMessage()));
        bar->setFormFactor(Plasma::Types::Horizontal);
        bar->setLocation(Plasma::Types::TopEdge);
        bar->config().group("Appearance").writeEntry("integratedBar", true);
        bar->configChanged();
        QQuickWindow window;
        window.resize(1280, 32);
        auto* item = PlasmaQuick::AppletQuickItem::itemForApplet(bar);
        QVERIFY(item);
        item->setParentItem(window.contentItem());
        item->setSize({1280,32});
        window.show();
        QTRY_VERIFY_WITH_TIMEOUT(item->fullRepresentationItem(), 10000);
        QTRY_COMPARE_WITH_TIMEOUT(bar->applets().size(), 2, 10000);
        const auto originalChildren = bar->applets();
        for (auto* child : originalChildren) {
            QVERIFY2(!child->failedToLaunch(), qPrintable(child->launchErrorMessage()));
            auto* childItem = PlasmaQuick::AppletQuickItem::itemForApplet(child);
            QVERIFY(childItem);
            QVERIFY(child->configScheme());
            if (child->pluginMetaData().pluginId() == QStringLiteral("org.kde.plasma.digitalclock")) {
                auto *setting = child->configScheme()->findItemByName("customDateFormat");
                QVERIFY(setting);
                QCOMPARE(setting->property().toString(), QString("ddd d ' | '"));
                auto *automaticFont = child->configScheme()->findItemByName("autoFontAndSize");
                QVERIFY(automaticFont);
                QVERIFY(!automaticFont->property().toBool());
                QCOMPARE(child->config().group("Appearance").readEntry("fontSize", 0), 10);
            } else {
                auto *setting = child->configScheme()->findItemByName("hiddenItems");
                QVERIFY(setting);
                QVERIFY(setting->property().toStringList().contains("org.kde.kdeconnect"));
            }
            QTRY_VERIFY(childItem->width() > 0);
            QVERIFY(childItem->window() == &window);
            const auto topLeft = childItem->mapToScene({0, 0});
            QVERIFY(topLeft.x() >= 0);
            QVERIFY(topLeft.x() + childItem->width() <= window.width() + 1);
            QCOMPARE(childItem->height(), 32);
            child->config().group("Appearance").writeEntry("testSavedChoice", "retained");
        }
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
        bar->config().group("Appearance").writeEntry("integratedBar", false);
        bar->configChanged();
        auto *representation = item->fullRepresentationItem();
        auto *viewport = representation->findChild<QQuickItem *>(QStringLiteral("menuViewport"));
        QVERIFY(viewport);
        // A normal panel allocates the advertised minimum to non-expanding
        // applets. It must include every menu, not just Apple + the app name.
        QQmlProperty minimumWidth(representation, QStringLiteral("Layout.minimumWidth"), qmlContext(representation));
        QVERIFY(minimumWidth.isValid());
        QTRY_VERIFY(minimumWidth.read().toReal() > 250);
        const qreal minimum = minimumWidth.read().toReal();
        item->setWidth(minimum);
        QTRY_VERIFY(viewport->width() + 1 >= viewport->property("contentWidth").toReal());
        item->setWidth(1280);
        bar->config().group("Appearance").writeEntry("integratedBar", true);
        bar->configChanged();
        QCoreApplication::processEvents();
        QCOMPARE(bar->applets(), originalChildren);
        for (auto* child : originalChildren) {
            QCOMPARE(child->config().group("Appearance").readEntry("testSavedChoice", QString()), QString("retained"));
            QTRY_VERIFY(PlasmaQuick::AppletQuickItem::itemForApplet(child)->isVisible());
        }
    }
};
QTEST_MAIN(CompositionTest)
#include "composition_test.moc"
