// SPDX-License-Identifier: GPL-3.0-or-later
#include "appmenuapplet.h"
#include "appmenumodel.h"
#include "dbusmenutypes_p.h"
#include <QApplication>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusVariant>
#include <QMenu>
#include <QMouseEvent>
#include <abstracttasksmodel.h>
#include <QProcess>
#include <QQuickItem>
#include <QQuickWindow>
#include <QSignalSpy>
#include <QSettings>
#include <QStandardPaths>
#include <QStandardItemModel>
#include <QTest>
#include <QTemporaryDir>
#include <QFile>
#include <QFileInfo>
#include <QAbstractProxyModel>
#include <QImage>

class RecordingTasks : public TaskManager::AbstractTasksModel
{
    Q_OBJECT
public:
    QList<QMap<int, QVariant>> rows{QMap<int, QVariant>{}};
    int rowCount(const QModelIndex &parent = {}) const override { return parent.isValid() ? 0 : rows.size(); }
    QVariant data(const QModelIndex &index, int role) const override {
        return index.isValid() && index.row() < rows.size() ? rows.at(index.row()).value(role) : QVariant();
    }
    void requestClose(const QModelIndex &index) override { Q_EMIT requested("close", index.row()); }
    void requestToggleMinimized(const QModelIndex &index) override { Q_EMIT requested("minimize", index.row()); }
    void requestToggleMaximized(const QModelIndex &index) override { Q_EMIT requested("maximize", index.row()); }
    void requestToggleFullScreen(const QModelIndex &index) override { Q_EMIT requested("fullscreen", index.row()); }
    void removeFirst() { beginRemoveRows({}, 0, 0); rows.removeFirst(); endRemoveRows(); }
Q_SIGNALS:
    void requested(const QString &action, int row);
};

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
        DBusMenuLayoutItem edit {3, {{QStringLiteral("label"), QStringLiteral("Edit")},
            {QStringLiteral("children-display"), QStringLiteral("submenu")}},
            {{4, {{QStringLiteral("label"), QStringLiteral("Copy")}}, {}}}};
        layout = parent == 1 ? file : parent == 3 ? edit : DBusMenuLayoutItem {0, {}, {file, edit}};
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
    void liveWindowControls()
    {
        if (!qEnvironmentVariableIsSet("MTTKDE_LIVE_GLOBALMENU"))
            QSKIP("Opt-in check for the disposable Plasma VM");
        using Roles = TaskManager::AbstractTasksModel;
        AppMenuModel model;
        model.tasksModel()->setGroupMode(TaskManager::TasksModel::GroupDisabled);
        QQuickWindow target;
        target.setTitle(QStringLiteral("Generic About live test"));
        target.resize(640, 400);
        QQuickItem anchor(target.contentItem());
        anchor.setSize({100, 24});
        target.show();
        target.requestActivate();
        QTRY_VERIFY_WITH_TIMEOUT(target.isActive(), 10000);
        QTRY_COMPARE_WITH_TIMEOUT(model.tasksModel()->activeTask().data(Roles::AppPid).toLongLong(), QCoreApplication::applicationPid(), 10000);
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        auto click = [&](const QString &label) {
            for (int row = 0; row < model.rowCount(); ++row) {
                auto *action = model.index(row).data(AppMenuModel::ActionRole).value<QAction*>();
                if (action && action->menu() && action->menu()->property("tahoeWindowView").toBool()) {
                    applet.trigger(&anchor, row);
                    break;
                }
            }
            auto *popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
            if (!popup) return false;
            for (auto *action : popup->actions()) {
                if (action->text() == label && action->isEnabled()) {
                    QTest::mouseClick(popup, Qt::LeftButton, Qt::NoModifier, popup->actionGeometry(action).center());
                    return true;
                }
            }
            popup->hide();
            return false;
        };
        QSignalSpy about(&applet, &AppMenuApplet::applicationAboutRequested);
        applet.triggerWindowMenu(&anchor);
        auto *popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        QVERIFY(popup);
        QTest::mouseClick(popup, Qt::LeftButton, Qt::NoModifier, popup->actionGeometry(popup->actions().first()).center());
        QTRY_COMPARE(about.count(), 1);
        const auto info = about.first().first().toMap();
        QVERIFY(!info.value("name").toString().isEmpty());
        QCOMPARE(info.value("processId").toString(), QString::number(QCoreApplication::applicationPid()));
        QCOMPARE(info.value("executable").toString(), QFileInfo(QCoreApplication::applicationFilePath()).canonicalFilePath());
        QVERIFY(click("Zoom"));
        QTRY_COMPARE(target.visibility(), QWindow::Maximized);
        QTRY_VERIFY(model.tasksModel()->activeTask().data(Roles::IsMaximized).toBool());
        QVERIFY(click("Restore"));
        QTRY_COMPARE(target.visibility(), QWindow::Windowed);
        QVERIFY(click("Enter Full Screen"));
        QTRY_COMPARE(target.visibility(), QWindow::FullScreen);
        QTRY_VERIFY(model.tasksModel()->activeTask().data(Roles::IsFullScreen).toBool());
        QVERIFY(click("Exit Full Screen"));
        QTRY_COMPARE(target.visibility(), QWindow::Windowed);
        const QPersistentModelIndex task(model.tasksModel()->activeTask());
        QVERIFY(click("Minimize"));
        QTRY_VERIFY(task.data(Roles::IsMinimized).toBool());
        QTRY_VERIFY(target.visibility() == QWindow::Minimized || !target.isExposed());
        model.tasksModel()->requestActivate(task);
        QTRY_VERIFY(target.isActive());
        QTRY_VERIFY(!task.data(Roles::IsMinimized).toBool());
        QVERIFY(click("Close Window"));
        QTRY_VERIFY(!target.isVisible());
    }
    void applicationAboutAndWindowActions()
    {
        using Roles = TaskManager::AbstractTasksModel;
        RecordingTasks source;
        source.rows[0] = {{Roles::IsWindow, true}, {Roles::IsActive, true},
                         {Roles::WinIdList, QVariantList{101}}, {Roles::AppName, "Editor & <Notes>"},
                         {Roles::GenericName, "Text editor"}, {Roles::AppId, "org.example.Editor"},
                         {Roles::AppPid, QCoreApplication::applicationPid()}};
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const auto iconPath = directory.filePath("editor.png");
        QImage icon(32, 32, QImage::Format_ARGB32);
        icon.fill(Qt::blue);
        QVERIFY(icon.save(iconPath));
        const auto path = directory.filePath("editor.desktop");
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("[Desktop Entry]\nType=Application\nName=Wrong app\nGenericName=Wrong description\nIcon=" + iconPath.toUtf8() + "\nVersion=1.0\nExec=/must/never/be/executed --secret\n");
        file.close();
        source.rows[0][Roles::LauncherUrlWithoutIcon] = QUrl::fromLocalFile(path);
        AppMenuModel model;
        QTRY_VERIFY(model.tasksModel()->sourceModel());
        auto *requestProxy = qobject_cast<QAbstractProxyModel*>(model.tasksModel()->sourceModel());
        QVERIFY(requestProxy);
        requestProxy->setSourceModel(&source);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QQuickWindow window;
        window.resize(500, 32);
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        window.show();
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        QSignalSpy requested(&source, &RecordingTasks::requested);
        QSignalSpy about(&applet, &AppMenuApplet::applicationAboutRequested);
        const QList<int> capabilities{Roles::IsClosable, Roles::IsMinimizable,
                                      Roles::IsMaximizable, Roles::IsFullScreenable};
        const QStringList commands{"close", "minimize", "maximize", "fullscreen"};
        // Exercise capability changes and both toggle labels on a cached popup.
        for (int state = 0; state < 16; ++state) {
            for (int bit = 0; bit < capabilities.size(); ++bit)
                source.rows[0][capabilities[bit]] = bool(state & (1 << bit));
            source.rows[0][Roles::IsMaximized] = bool(state & 1);
            source.rows[0][Roles::IsFullScreen] = bool(state & 2);
            Q_EMIT source.dataChanged(source.index(0), source.index(0));
            applet.triggerWindowMenu(&anchor);
            auto *popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
            QVERIFY(popup);
            QList<QAction*> actions;
            for (auto *action : popup->actions()) if (!action->isSeparator()) actions << action;
            QCOMPARE(actions.size(), 2);
            QCOMPARE(actions[0]->text(), QString("About Editor && <Notes>"));
            QCOMPARE(actions[1]->text(), QString("Close Editor && <Notes>"));
            QCOMPARE(actions[1]->isEnabled(), bool(state & 1));
            popup->hide();
            QMenu view;
            auto *native = view.addAction("Application view action");
            model.refreshWindowActions(&view);
            model.refreshWindowActions(&view); // no duplicates; exporter action survives
            QCOMPARE(view.actions().first(), native);
            actions.clear();
            for (auto *action : view.actions())
                if (!action->isSeparator() && action != native) actions << action;
            QCOMPARE(actions.size(), 4);
            QCOMPARE(actions[2]->text(), QString(state & 1 ? "Restore" : "Zoom"));
            QCOMPARE(actions[3]->text(), QString(state & 2 ? "Exit Full Screen" : "Enter Full Screen"));
            for (int bit = 0; bit < capabilities.size(); ++bit) {
                QCOMPARE(actions[bit]->isEnabled(), bool(state & (1 << bit)));
                const auto count = requested.count();
                actions[bit]->trigger();
                QCOMPARE(requested.count(), count + bool(state & (1 << bit)));
                if (requested.count() > count) {
                    QCOMPARE(requested.last().at(0).toString(), commands[bit]);
                    QCOMPARE(requested.last().at(1).toInt(), 0);
                }
            }
            popup->hide();
        }
        applet.triggerWindowMenu(&anchor);
        auto *popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        QVERIFY(popup);
        auto *aboutAction = popup->actions().first();
        popup->hide();
        aboutAction->trigger();
        QTRY_COMPARE(about.count(), 1);
        const auto info = about.first().first().toMap();
        QCOMPARE(info.value("name").toString(), QString("Editor & <Notes>"));
        QCOMPARE(info.value("description").toString(), QString("Text editor"));
        QCOMPARE(info.value("desktopFile").toString(), path);
        QCOMPARE(info.value("executable").toString(), QFileInfo(QCoreApplication::applicationFilePath()).canonicalFilePath());
        QCOMPARE(info.value("processId").toString(), QString::number(QCoreApplication::applicationPid()));
        QVERIFY(!qvariant_cast<QIcon>(info.value("icon")).isNull());
        QVERIFY(!info.contains("version")); // Desktop Entry Version is a file-format version.
        QVERIFY(!info.contains("commandLine"));
        // Deleted tasks must never become another app's window action.
        QMenu staleView;
        model.refreshWindowActions(&staleView);
        const auto count = requested.count();
        source.removeFirst();
        for (auto *action : staleView.actions()) if (!action->isSeparator()) action->trigger();
        for (auto *action : popup->actions()) if (!action->isSeparator()) action->trigger();
        QTest::qWait(20);
        QCOMPARE(requested.count(), count);
        QCOMPARE(about.count(), 1);
    }
    void mouseAcrossEntireBar_data()
    {
        QTest::addColumn<bool>("exported");
        QTest::newRow("generic") << false;
        QTest::newRow("exported") << true;
    }
    void mouseAcrossEntireBar()
    {
        QFETCH(bool, exported);
        QProcess exporter;
        if (exported) {
            exporter.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--exporter")});
            QVERIFY(exporter.waitForStarted());
            QVERIFY(exporter.waitForReadyRead());
        }
        using Roles = TaskManager::AbstractTasksModel;
        QStandardItemModel tasks(1, 1);
        auto task = tasks.index(0, 0);
        tasks.setData(task, true, Roles::IsWindow);
        tasks.setData(task, true, Roles::IsActive);
        tasks.setData(task, true, Roles::IsClosable);
        tasks.setData(task, QVariantList{101}, Roles::WinIdList);
        tasks.setData(task, QStringLiteral("Test application"), Roles::AppName);
        AppMenuModel model;
        model.setEnableMenuSearch(false);
        QTRY_VERIFY(model.tasksModel()->sourceModel());
        model.tasksModel()->setSourceModel(&tasks);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTRY_COMPARE(model.rowCount(), 2);
        if (exported) {
            model.updateApplicationMenu("org.mttkde.PopupTest", "/Menu");
            QTRY_COMPARE(model.rowCount(), 3);
        }
        QQuickWindow window;
        window.resize(400, 24);
        QQuickItem grid(window.contentItem());
        grid.setSize({400, 24});
        QQuickItem apple(&grid), appName(&grid), file(&grid), edit(&grid);
        const QList<QQuickItem*> buttons{&apple, &appName, &file, &edit};
        const QList<int> indices{-3, -2, 0, 1};
        for (int i = 0; i < buttons.size(); ++i) {
            buttons[i]->setPosition({qreal(i * 80), 0});
            buttons[i]->setSize({80, 24});
            buttons[i]->setProperty("buttonIndex", indices[i]);
        }
        window.show();
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        applet.setModel(&model);
        applet.setButtonGrid(&grid);
        connect(&applet, &AppMenuApplet::requestActivateIndex, &applet, [&](int index) {
            if (index == -3) applet.triggerSystemMenu(&apple);
            else if (index == -2) applet.triggerWindowMenu(&appName);
            else applet.trigger(buttons[indices.indexOf(index)], index);
        });
        applet.triggerSystemMenu(&apple);
        auto* popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
        QVERIFY(popup);
        const auto popupId = popup->winId();
        auto* systemStyle = popup->style();
        QSignalSpy hidden(popup, &QMenu::aboutToHide);
        QSignalSpy selected(&applet, &AppMenuApplet::currentIndexChanged);
        for (int index : {-2, 0, 1, 0, -2, -3, 1, -3}) {
            auto* button = buttons[indices.indexOf(index)];
            const QPointF global = button->mapToGlobal(QPointF(40, 12));
            QMouseEvent move(QEvent::MouseMove, popup->mapFromGlobal(global.toPoint()), global,
                             Qt::NoButton, Qt::NoButton, Qt::NoModifier);
            QApplication::sendEvent(popup, &move);
            QCOMPARE(applet.currentIndex(), index);
            QCOMPARE(QApplication::activePopupWidget(), popup);
            QCOMPARE(popup->winId(), popupId);
            QCOMPARE(hidden.count(), 0);
            QVERIFY(!popup->actions().isEmpty());
            QCOMPARE(popup->style() == systemStyle, index == -3);
        }
        QCOMPARE(selected.count(), 8); // no intermediate closed/highlight-lost state
        QTest::keyClick(popup, Qt::Key_Escape);
        QCOMPARE(applet.currentIndex(), -1);
        QCOMPARE(hidden.count(), 1);
        applet.trigger(&file, 0);
        QCOMPARE(applet.currentIndex(), 0);
        popup->hide();
        auto* source = model.index(0).data(AppMenuModel::ActionRole).value<QAction*>()->menu();
        QVERIFY(source != popup);
        QVERIFY(!source->actions().isEmpty());
        if (exported) {
            exporter.terminate();
            QVERIFY(exporter.waitForFinished());
        }
    }
    void systemMenuIconPresets()
    {
        QQuickWindow window;
        window.resize(400, 100);
        window.show();
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        QSettings settings(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
                           + QStringLiteral("/kdeglobals"), QSettings::IniFormat);
        for (const auto* preset : {"tahoe", "golden-gate", "tahoe"}) {
            settings.setValue(QStringLiteral("MacTahoeLiquidKde/SystemMenuPreset"), QString::fromLatin1(preset));
            settings.sync();
            applet.triggerSystemMenu(&anchor);
            auto* popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
            QVERIFY(popup);
            int row = 0;
            for (auto* action : popup->actions()) {
                if (action->isSeparator()) continue;
                const bool featured = row < 2 || action->text().startsWith(QLatin1String("App Store"));
                QCOMPARE(action->icon().isNull(), QString::fromLatin1(preset) == QLatin1String("golden-gate") && !featured);
                ++row;
            }
            QVERIFY(row >= 8);
            popup->hide();
        }
    }
    void systemMenuShortcuts()
    {
        QQuickWindow window;
        window.resize(400, 100);
        window.show();
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        AppMenuApplet applet(nullptr, KPluginMetaData(), {});
        for (auto modifiers : {Qt::ControlModifier | Qt::MetaModifier,
                               Qt::ShiftModifier | Qt::MetaModifier}) {
            applet.triggerSystemMenu(&anchor);
            auto* popup = qobject_cast<QMenu*>(QApplication::activePopupWidget());
            QVERIFY(popup);
            auto* action = popup->actions().at(popup->actions().size() - (modifiers.testFlag(Qt::ControlModifier) ? 2 : 1));
            QCOMPARE(action->shortcut(), QKeySequence(modifiers | Qt::Key_Q));
            // Exercise activation without calling the session lock/logout service.
            action->disconnect();
            QSignalSpy triggered(action, &QAction::triggered);
            QTest::keyClick(popup, Qt::Key_Q, modifiers);
            QTRY_COMPARE(triggered.count(), 1);
            popup->hide();
        }
    }
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
    void changingViewAndDestroyingAppletPreservesSourceActions()
    {
        QMenu root;
        auto* file = root.addMenu("File");
        auto* open = file->addAction("Open");
        QStandardItemModel model(1, 1);
        model.setData(model.index(0, 0), QVariant::fromValue(file->menuAction()), AppMenuModel::ActionRole);
        QQuickWindow window;
        QQuickItem anchor(window.contentItem());
        anchor.setSize({80, 24});
        {
            AppMenuApplet applet(nullptr, KPluginMetaData(), {});
            applet.setModel(&model);
            applet.trigger(&anchor, 0);
            QCOMPARE(applet.currentIndex(), 0);
            applet.setView(AppMenuApplet::CompactView);
            QCOMPARE(applet.currentIndex(), -1);
            QCOMPARE(file->actions(), QList<QAction*>{open});
            QCOMPARE(file->menuAction()->menu(), file);
            applet.setView(AppMenuApplet::FullView);
            applet.trigger(&anchor, 0);
            QCOMPARE(applet.currentIndex(), 0);
        }
        QCOMPARE(file->actions(), QList<QAction*>{open});
        QCOMPARE(file->menuAction()->menu(), file);
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
        model.setEnableMenuSearch(false);
        model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus);
        model.updateApplicationMenu("org.mttkde.PopupTest", "/Menu");
        QTRY_COMPARE(model.rowCount(), 2);
        auto* action = model.index(0, 0).data(AppMenuModel::ActionRole).value<QAction*>();
        QVERIFY(action && action->menu());
        QTRY_COMPARE(action->menu()->actions().size(), 1);
        const int initial = openings();
        QQuickWindow window;
        window.resize(400, 100);
        window.show();
        QVERIFY(QTest::qWaitForWindowExposed(&window));
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
