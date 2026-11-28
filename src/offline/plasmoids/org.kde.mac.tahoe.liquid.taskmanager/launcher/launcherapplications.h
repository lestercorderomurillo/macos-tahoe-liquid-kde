// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <KIO/ApplicationLauncherJob>
#include <KService>
#include <KGlobalAccel>
#include <QAction>
#include <QQuickItem>
#include <QVariantList>
#include <qqmlregistration.h>
#include <algorithm>

class LauncherApplications : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    Q_INVOKABLE void registerSearchShortcut(QQuickItem *launcher, const QString &label) {
        // Plasma may load more than one launcher or recreate its QML engine.
        // Keep one shortcut and let a surviving applet handle activation.
        static QList<QQuickItem *> launchers;
        static QAction *action = nullptr;
        if (!launcher || launchers.contains(launcher)) return;
        launchers.append(launcher);
        connect(launcher, &QObject::destroyed, [launcher] {
            launchers.removeAll(launcher);
            if (launchers.isEmpty()) {
                delete action;
                action = nullptr;
            }
        });
        if (action) return;
        action = new QAction(label);
        action->setObjectName(QStringLiteral("mac-launchpad-floating-search"));
        connect(action, &QAction::triggered, [] {
            if (!launchers.isEmpty())
                QMetaObject::invokeMethod(launchers.first(), "toggleFloatingSearch");
        });
        const QKeySequence preferred(Qt::ALT | Qt::Key_Space);
        const QKeySequence fallback(Qt::ALT | Qt::META | Qt::Key_Space);
        KGlobalAccel::setGlobalShortcut(action, KGlobalAccel::isGlobalShortcutAvailable(preferred) ? preferred : fallback);
    }

    Q_INVOKABLE void restackReusedDelegate(QQuickItem *item) const {
        if (!item || !item->parentItem()) return;
        const auto siblings = item->parentItem()->childItems();
        if (!siblings.isEmpty() && siblings.constLast() != item)
            item->stackAfter(siblings.constLast());
    }
    Q_INVOKABLE QVariantList choices() const {
        QVariantList apps;
        for (const auto &service : KService::allServices()) {
            if (service->isApplication() && !service->noDisplay())
                apps.append(QVariantMap{{QStringLiteral("name"), service->name()},
                                        {QStringLiteral("id"), service->storageId()}});
        }
        std::sort(apps.begin(), apps.end(), [](const QVariant &a, const QVariant &b) {
            return QString::localeAwareCompare(a.toMap().value(QStringLiteral("name")).toString(),
                                               b.toMap().value(QStringLiteral("name")).toString()) < 0;
        });
        return apps;
    }
    Q_INVOKABLE bool open(const QString &id) {
        auto service = KService::serviceByStorageId(id);
        if (!service || !service->isApplication()) return false;
        (new KIO::ApplicationLauncherJob(service))->start();
        return true;
    }
};
