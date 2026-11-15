// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QUrl>
#include <qqmlregistration.h>

// Read history only while its view is open. Never enable recording implicitly.
class ClipboardModel : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY activeChanged)
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(QVariantList entries READ entries NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
public:
    explicit ClipboardModel(QObject *parent = nullptr) : QObject(parent),
        m_service(service(), QDBusConnection::sessionBus(), QDBusServiceWatcher::WatchForOwnerChange)
    {
        QDBusConnection::sessionBus().connect(service(), QStringLiteral("/Clipboard"), service(),
            QStringLiteral("changed"), this, SLOT(refresh()));
        connect(&m_service, &QDBusServiceWatcher::serviceOwnerChanged, this,
            [this] { refresh(); });
    }
    bool active() const { return m_active; }
    bool available() const { return m_available; }
    QVariantList entries() const { return m_entries; }
    QString error() const { return m_error; }
    void setActive(bool value) {
        if (m_active == value) return;
        m_active = value;
        ++m_generation;
        ++m_activation;
        if (value) refresh();
        else { m_entries.clear(); m_error.clear(); Q_EMIT changed(); }
        Q_EMIT activeChanged();
    }
    Q_INVOKABLE void copy(const QString &id) { action(QStringLiteral("copy"), {id}, true); }
    Q_INVOKABLE void remove(const QString &id) { action(QStringLiteral("remove"), {id}); }
    Q_INVOKABLE void pin(const QString &id, bool value) { action(QStringLiteral("setPinned"), {id, value}); }
    Q_INVOKABLE void clear() { action(QStringLiteral("clearHistory"), {}); }
public Q_SLOTS:
    void refresh() {
        if (!m_active) return;
        const auto generation = ++m_generation;
        auto *watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message(QStringLiteral("list"))), this);
        connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, watcher, generation] {
            QDBusPendingReply<QString> reply = *watcher;
            watcher->deleteLater();
            if (!m_active || generation != m_generation) return;
            m_entries.clear();
            QJsonParseError parse;
            const auto document = QJsonDocument::fromJson(reply.isError() ? QByteArray() : reply.value().toUtf8(), &parse);
            m_available = !reply.isError() && parse.error == QJsonParseError::NoError && document.isArray();
            if (m_available) {
                for (const auto &value : document.array()) {
                    const auto item = value.toObject();
                    if (item.value(QStringLiteral("id")).toString().isEmpty()) continue;
                    const auto kind = item.value(QStringLiteral("kind")).toString();
                    if (kind != QStringLiteral("text") && kind != QStringLiteral("image")) continue;
                    auto map = item.toVariantMap();
                    // Encode local filenames, never interpret clipboard data as URLs or markup.
                    map.insert(QStringLiteral("imageUrl"), QUrl::fromLocalFile(item.value(QStringLiteral("path")).toString()));
                    m_entries.append(map);
                }
            }
            Q_EMIT changed();
        });
    }
Q_SIGNALS:
    void activeChanged();
    void changed();
    void copied();
private:
    static QString service() { return QStringLiteral("org.mactahoe.Clipboard"); }
    static QDBusMessage message(const QString &method) {
        auto msg = QDBusMessage::createMethodCall(service(), QStringLiteral("/Clipboard"), service(), method);
        msg.setAutoStartService(false);
        return msg;
    }
    void action(const QString &method, const QVariantList &args, bool copying = false) {
        if (!m_active || !m_available) return;
        const auto activation = m_activation;
        auto msg = message(method); msg.setArguments(args);
        auto *watcher = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
        connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, watcher, copying, activation] {
            const QDBusPendingReply<> reply = *watcher;
            watcher->deleteLater();
            if (!m_active || activation != m_activation) return;
            m_error = reply.isError() ? tr("Clipboard action failed. Try again.") : QString();
            Q_EMIT changed();
            if (!reply.isError() && copying) Q_EMIT copied();
            else refresh();
        });
    }
    QDBusServiceWatcher m_service;
    QVariantList m_entries;
    QString m_error;
    quint64 m_generation = 0, m_activation = 0;
    bool m_active = false, m_available = false;
};
