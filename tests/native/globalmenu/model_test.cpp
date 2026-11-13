// SPDX-License-Identifier: GPL-3.0-or-later
#include "appmenumodel.h"
#include "quickbarmenuhelpers.h"
#include <QMenu>
#include <QLineEdit>
#include "dbusmenutypes_p.h"
#include "dbusmenuimporter.h"
#include <abstracttasksmodel.h>

#include <QDBusConnection>
#include <QDBusVariant>
#include <QDBusInterface>
#include <QApplication>
#include <QProcess>
#include <QSignalSpy>
#include <QStandardItemModel>
#include <QTest>
#include <QWindow>
#include <netwm.h>
#include <xcb/xcb.h>

class MenuExporter : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "com.canonical.dbusmenu")
public:
    QStringList labels {QStringLiteral("File"), QStringLiteral("Edit")};
    uint revision = 1;

public Q_SLOTS:
    uint GetLayout(int, int, const QStringList&, DBusMenuLayoutItem& layout)
    {
        layout = {0, {}, {}};
        int id = 1;
        for (const auto& label : labels) {
            layout.children.append({id++, {{QStringLiteral("label"), label}}, {}});
        }
        return revision;
    }
    bool AboutToShow(int) { return false; }
    void SetLabels(const QStringList& values)
    {
        labels = values;
        Q_EMIT LayoutUpdated(++revision, 0);
    }
    void Event(int, const QString&, const QDBusVariant&, uint) { }

Q_SIGNALS:
    void LayoutUpdated(uint revision, int parent);
};

class ModelTest : public QObject
{
    Q_OBJECT
    const QString service = QStringLiteral("org.mttkde.MenuTest");
    const QString path = QStringLiteral("/Menu");
    QProcess exporter;
    void setLabels(const QStringList& labels)
    {
        QDBusInterface remote(service, path, QStringLiteral("com.canonical.dbusmenu"));
        QVERIFY(remote.call(QStringLiteral("SetLabels"), labels).type() != QDBusMessage::ErrorMessage);
    }

private Q_SLOTS:
    void initTestCase()
    {
        DBusMenuTypes_register();
        QVERIFY(QDBusConnection::sessionBus().isConnected());
    }
    void init()
    {
        exporter.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--exporter")});
        QVERIFY(exporter.waitForStarted());
        QVERIFY(exporter.waitForReadyRead());
        QCOMPARE(exporter.readAllStandardOutput().trimmed(), QByteArray("ready"));
    }
    void cleanup()
    {
        exporter.terminate();
        QVERIFY(exporter.waitForFinished());
        QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
    }
    void genericMenuFollowsWindowAndYieldsToExporter()
    {
        using Roles = TaskManager::AbstractTasksModel;
        QStandardItemModel tasks(2, 1);
        const auto first = tasks.index(0, 0);
        const auto second = tasks.index(1, 0);
        for (const auto &idx : {first, second}) {
            tasks.setData(idx, true, Roles::IsWindow);
            tasks.setData(idx, QVariantList{idx.row() + 1}, Roles::WinIdList);
        }
        tasks.setData(first, true, Roles::IsActive);
        tasks.setData(first, true, Roles::IsClosable);
        tasks.setData(first, true, Roles::IsMaximizable);
        AppMenuModel model;
        model.setEnableMenuSearch(false);
        QTRY_VERIFY(model.tasksModel()->sourceModel());
        model.tasksModel()->setSourceModel(&tasks);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTRY_COMPARE(model.rowCount(), 2);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QString("&Edit"));
        auto actionAt = [&model](int row) {
            return model.index(row).data(AppMenuModel::ActionRole).value<QAction *>();
        };
        QVERIFY(actionAt(1)->menu()->actions().first()->isEnabled());
        QPointer<QAction> oldAction = actionAt(0);
        model.setEnableGenericMenu(false);
        QTRY_COMPARE(model.rowCount(), 0);
        QVERIFY(oldAction.isNull());
        model.setEnableGenericMenu(true);
        QTRY_COMPARE(model.rowCount(), 2);
        tasks.setData(first, service, Roles::ApplicationMenuServiceName);
        tasks.setData(first, path, Roles::ApplicationMenuObjectPath);
        QTRY_COMPARE(model.rowCount(), 3);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QString("File"));
        tasks.setData(first, false, Roles::IsActive);
        tasks.setData(second, true, Roles::IsActive);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTRY_COMPARE(model.rowCount(), 2);
        QVERIFY(!actionAt(1)->menu()->actions().first()->isEnabled());
        setLabels({});
        tasks.setData(second, service, Roles::ApplicationMenuServiceName);
        tasks.setData(second, path, Roles::ApplicationMenuObjectPath);
        QVERIFY(QMetaObject::invokeMethod(&model, "onActiveWindowChanged"));
        QCOMPARE(model.rowCount(), 0);
        QTRY_COMPARE(model.rowCount(), 2);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QString("&Edit"));
        model.setEnableGenericMenu(false);
        QTRY_COMPARE(model.rowCount(), 0);
        model.setEnableGenericMenu(true);
        QTRY_COMPARE(model.rowCount(), 2);
        setLabels({"File", "Edit"});
        QTRY_COMPARE(model.rowCount(), 3);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QString("File"));
        tasks.setData(second, QString(), Roles::ApplicationMenuServiceName);
        tasks.setData(second, QString(), Roles::ApplicationMenuObjectPath);
        QTRY_COMPARE(model.rowCount(), 2);
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        tasks.removeRow(1);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTRY_COMPARE(model.rowCount(), 0);
    }
    void fallbackShortcutRequiresTheOriginalWindow()
    {
        if (QGuiApplication::platformName() != QStringLiteral("xcb")) {
            QSKIP("Keyboard dispatch requires the private Xvfb session");
        }
        using Roles = TaskManager::AbstractTasksModel;
        QStandardItemModel tasks(2, 1);
        const auto first = tasks.index(0, 0);
        const auto second = tasks.index(1, 0);
        for (auto idx : {first, second}) {
            tasks.setData(idx, true, Roles::IsWindow);
            tasks.setData(idx, QVariantList{idx.row() + 1}, Roles::WinIdList);
        }
        tasks.setData(first, true, Roles::IsActive);
        AppMenuModel model;
        model.setEnableMenuSearch(false);
        QTRY_VERIFY(model.tasksModel()->sourceModel());
        model.tasksModel()->setSourceModel(&tasks);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTRY_COMPARE(model.rowCount(), 2);
        QLineEdit editor(QStringLiteral("Original document"));
        editor.show();
        auto *connection = xcb_connect(nullptr, nullptr);
        QVERIFY(!xcb_connection_has_error(connection));
        xcb_set_input_focus(connection, XCB_INPUT_FOCUS_POINTER_ROOT, editor.winId(), XCB_CURRENT_TIME);
        xcb_flush(connection);
        QTRY_VERIFY(editor.hasFocus());
        auto selectAll = [&model]() {
            auto *edit = model.index(0).data(AppMenuModel::ActionRole).value<QAction *>()->menu();
            return edit->actions().last();
        };
        QVERIFY(selectAll()->isEnabled());
        selectAll()->trigger();
        QTRY_COMPARE(editor.selectedText(), QStringLiteral("Original document"));
        editor.deselect();
        selectAll()->trigger();
        tasks.setData(first, false, Roles::IsActive);
        tasks.setData(second, true, Roles::IsActive);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTest::qWait(180);
        QVERIFY(editor.selectedText().isEmpty());
        // Deletion invalidates the persistent task even while the popup keeps
        // the panel accepting input.
        selectAll()->trigger();
        model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus);
        tasks.removeRow(1);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTest::qWait(180);
        QVERIFY(editor.selectedText().isEmpty());
        xcb_disconnect(connection);
    }
    void searchesAttachedMenusWithoutMnemonicMarkers()
    {
        QMenu root;
        QMenu externallyOwned;
        auto* open = externallyOwned.addAction("&Open");
        auto* disabled = externallyOwned.addAction("Disabled");
        disabled->setEnabled(false);
        auto* hidden = externallyOwned.addAction("Hidden");
        hidden->setVisible(false);
        externallyOwned.addSeparator();
        root.addMenu(&externallyOwned);
        externallyOwned.addMenu(&root); // malformed/cyclic exporter must terminate
        QList<QAction*> actions;
        QSet<QMenu*> visited;
        QuickBarMenu::collectMenuActions(&root, actions, visited);
        QCOMPARE(actions, QList<QAction*>{open});
        QCOMPARE(QuickBarMenu::visibleMenuText("Save && E&xit"), QString("Save & Exit"));
    }
    void searchCanBeEnabledOnEitherBackend()
    {
        AppMenuModel model;
        model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus);
        model.setEnableMenuSearch(false);
        model.updateApplicationMenu(service, path);
        QTRY_COMPARE(model.rowCount(), 2);
        model.setEnableMenuSearch(true);
        QTRY_COMPARE(model.rowCount(), 3);
        QCOMPARE(model.index(2).data(AppMenuModel::MenuRole).toString(), QString("Search"));
        model.setEnableMenuSearch(false);
        QTRY_COMPARE(model.rowCount(), 2);
    }
    void localActionsSurviveExporterRefresh()
    {
        DBusMenuImporter importer(service, path);
        importer.updateMenu();
        QTRY_VERIFY(importer.menu());
        QTRY_COMPARE(importer.menu()->actions().size(), 2);
        QPointer<QAction> local = importer.menu()->addAction("Local window action");
        for (const QStringList labels : {QStringList{"First", "Second", "Third"},
                                         QStringList{}, QStringList{"Restored"}}) {
            setLabels(labels);
            QTRY_COMPARE(importer.menu()->actions().size(), labels.size() + 1);
            QVERIFY(local);
            QCOMPARE(importer.menu()->actions().last(), local.data());
            for (int i = 0; i < labels.size(); ++i)
                QCOMPARE(importer.menu()->actions()[i]->text(), labels[i]);
        }
    }
    void switchesWithoutExposingPreviousActions()
    {
        AppMenuModel model;
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        model.updateApplicationMenu(service, path);
        QTRY_COMPARE(model.rowCount(), 2);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QStringLiteral("File"));
        model.updateApplicationMenu(service, QStringLiteral("/Missing"));
        QCOMPARE(model.rowCount(), 0);
        QVERIFY(!model.menuAvailable());
        model.updateApplicationMenu(service, path);
        QTRY_COMPARE(model.rowCount(), 2);
        model.updateApplicationMenu({}, {});
        QCOMPARE(model.rowCount(), 0);
        QVERIFY(!model.menuAvailable());
    }
    void recoversAfterExporterRestart()
    {
        AppMenuModel model;
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        model.updateApplicationMenu(service, path);
        QTRY_COMPARE(model.rowCount(), 2);
        exporter.terminate();
        QVERIFY(exporter.waitForFinished());
        QTRY_VERIFY(!model.menuAvailable());
        init();
        QTRY_COMPARE(model.rowCount(), 2);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QStringLiteral("File"));
    }
    void resumesAfterPanelReleasesFocus()
    {
        AppMenuModel model;
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        model.updateApplicationMenu(service, path);
        QTRY_COMPARE(model.rowCount(), 2);
        // The isolated offscreen session has no active application. A focus
        // update while the panel accepts input must retain the previous menu.
        QVERIFY(QMetaObject::invokeMethod(&model, "onActiveWindowChanged"));
        QCOMPARE(model.rowCount(), 2);
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::ActiveStatus));
        QTRY_COMPARE(model.rowCount(), 0);
        QVERIFY(!model.menuAvailable());
    }
    void activeApplicationWinsWhilePanelStillAcceptsInput()
    {
        using Roles = TaskManager::AbstractTasksModel;
        QStandardItemModel tasks(2, 1);
        const auto first = tasks.index(0, 0);
        const auto second = tasks.index(1, 0);
        tasks.setData(first, QVariantList{1}, Roles::WinIdList);
        tasks.setData(second, QVariantList{2}, Roles::WinIdList);
        tasks.setData(first, service, Roles::ApplicationMenuServiceName);
        tasks.setData(first, path, Roles::ApplicationMenuObjectPath);
        tasks.setData(second, true, Roles::IsActive);

        AppMenuModel model;
        QTRY_VERIFY(model.tasksModel()->sourceModel());
        model.tasksModel()->setSourceModel(&tasks);
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        QTRY_VERIFY(model.tasksModel()->activeTask().isValid());
        QCOMPARE(model.rowCount(), 0);
        auto activate = [&](const QModelIndex& previous, const QModelIndex& next) {
            tasks.setData(previous, false, Roles::IsActive);
            tasks.setData(next, true, Roles::IsActive);
            QCOMPARE(model.tasksModel()->activeTask().data(Roles::WinIdList),
                next.data(Roles::WinIdList));
            // Older SDKs emit this from their window backend, newer SDKs
            // from TasksModel itself. Supply the backend notification here.
            Q_EMIT model.tasksModel()->activeTaskChanged();
        };
        activate(second, first);
        QTRY_COMPARE(model.rowCount(), 3);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QStringLiteral("File"));
        activate(first, second);
        QTRY_COMPARE(model.rowCount(), 0);
        activate(second, first);
        QTRY_COMPARE(model.rowCount(), 3);
        tasks.setData(first, false, Roles::IsActive);
        Q_EMIT model.tasksModel()->activeTaskChanged();
        QTRY_VERIFY(!model.tasksModel()->activeTask().isValid());
        QCOMPARE(model.rowCount(), 3);
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::ActiveStatus));
        QTRY_COMPARE(model.rowCount(), 0);
    }
    void x11ActiveApplicationWinsWhilePanelStillAcceptsInput()
    {
#ifndef MTTKDE_HAS_X11_TASKS
        QSKIP("Plasma 6.8 and newer have no X11 task backend");
#endif
        if (!qEnvironmentVariableIsSet("MTTKDE_TEST_X11")) {
            QSKIP("Requires the isolated X11 server");
        }
        auto* connection = xcb_connect(nullptr, nullptr);
        QVERIFY(!xcb_connection_has_error(connection));
        const auto root = xcb_setup_roots_iterator(xcb_get_setup(connection)).data->root;
        auto setWindowProperty = [&](const char* name, const QList<xcb_window_t>& windows) {
            auto* reply = xcb_intern_atom_reply(connection,
                xcb_intern_atom(connection, false, strlen(name), name), nullptr);
            QVERIFY(reply);
            xcb_change_property(connection, XCB_PROP_MODE_REPLACE, root, reply->atom,
                XCB_ATOM_WINDOW, 32, windows.size(), windows.constData());
            free(reply);
            xcb_flush(connection);
        };
        QWindow first;
        QWindow second;
        first.setTitle(QStringLiteral("First application"));
        second.setTitle(QStringLiteral("Second application"));
        first.show();
        second.show();
        NETWinInfo info(connection, first.winId(), root, NET::Properties(), NET::Properties2());
        info.setAppMenuServiceName(service.toUtf8().constData());
        info.setAppMenuObjectPath(path.toUtf8().constData());
        setWindowProperty("_NET_CLIENT_LIST", {xcb_window_t(first.winId()), xcb_window_t(second.winId())});
        setWindowProperty("_NET_ACTIVE_WINDOW", {xcb_window_t(second.winId())});
        AppMenuModel model;
        model.setEnableGenericMenu(false);
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        QTRY_VERIFY(model.tasksModel()->activeTask().isValid());
        QCOMPARE(model.rowCount(), 0);
        setWindowProperty("_NET_ACTIVE_WINDOW", {xcb_window_t(first.winId())});
        QTRY_COMPARE(model.rowCount(), 3);
        QCOMPARE(model.index(0).data(AppMenuModel::MenuRole).toString(), QStringLiteral("File"));
        setWindowProperty("_NET_ACTIVE_WINDOW", {xcb_window_t(second.winId())});
        QTRY_COMPARE(model.rowCount(), 0);
        setWindowProperty("_NET_ACTIVE_WINDOW", {xcb_window_t(first.winId())});
        QTRY_COMPARE(model.rowCount(), 3);
        setWindowProperty("_NET_ACTIVE_WINDOW", {XCB_WINDOW_NONE});
        setWindowProperty("_NET_CLIENT_LIST", {});
        QTRY_VERIFY(!model.tasksModel()->activeTask().isValid());
        xcb_disconnect(connection);
    }
    void lateMenuAppearsAfterEmptyExport()
    {
        setLabels({});
        AppMenuModel model;
        QVERIFY(model.setProperty("containmentStatus", Plasma::Types::AcceptingInputStatus));
        model.updateApplicationMenu(service, path);
        QTRY_VERIFY(!model.menuAvailable());
        setLabels({QStringLiteral("Tools")});
        QTRY_COMPARE(model.rowCount(), model.tasksModel()->activeTask().isValid() ? 2 : 1);
        QVERIFY(model.menuAvailable());
    }
};

int main(int argc, char** argv)
{
    QApplication app(argc, argv);
    if (app.arguments().contains(QStringLiteral("--exporter"))) {
        DBusMenuTypes_register();
        MenuExporter exporter;
        auto bus = QDBusConnection::sessionBus();
        if (!bus.registerObject(QStringLiteral("/Menu"), &exporter,
                QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals)
            || !bus.registerService(QStringLiteral("org.mttkde.MenuTest"))) {
            return 1;
        }
        puts("ready");
        fflush(stdout);
        return app.exec();
    }
    ModelTest test;
    return QTest::qExec(&test, argc, argv);
}
#include "model_test.moc"
