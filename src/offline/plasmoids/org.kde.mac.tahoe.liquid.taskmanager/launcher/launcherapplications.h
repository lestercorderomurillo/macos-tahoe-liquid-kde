// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <KIO/ApplicationLauncherJob>
#include <KService>
#include <QQuickItem>
#include <QVariantList>
#include <qqmlregistration.h>
#include <algorithm>

class LauncherApplications : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
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
