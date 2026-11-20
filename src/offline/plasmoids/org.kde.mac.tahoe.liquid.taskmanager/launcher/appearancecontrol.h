// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <KConfigGroup>
#include <KSharedConfig>
#include <QDir>
#include <QFile>
#include <QFileSystemWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QStandardPaths>
#include <QtQml/qqmlregistration.h>

class AppearanceControl : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString preference READ preference NOTIFY preferenceChanged)
public:
    explicit AppearanceControl(QObject *parent = nullptr) : QObject(parent)
    {
        const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation)
            + QStringLiteral("/mac-tahoe-liquid-kde");
        stateFile = dir + QStringLiteral("/appearance.json");
        QDir().mkpath(dir);
        watcher.addPath(dir); // The switcher replaces its state file atomically.
        connect(&watcher, &QFileSystemWatcher::directoryChanged, this, &AppearanceControl::refresh);
        refresh();
    }

    QString preference() const { return current; }
    Q_INVOKABLE void refresh()
    {
        QFile file(stateFile);
        QString selection;
        if (file.open(QIODevice::ReadOnly))
            selection = QJsonDocument::fromJson(file.readAll()).object().value(QStringLiteral("preference")).toString();
        if (selection == QStringLiteral("native-auto")) selection = QStringLiteral("auto");
        if (selection.isEmpty()) {
            auto config = KSharedConfig::openConfig(QStringLiteral("kdeglobals"));
            if (KConfigGroup(config, QStringLiteral("KDE")).readEntry("AutomaticLookAndFeel", false))
                selection = QStringLiteral("auto");
            else selection = KConfigGroup(config, QStringLiteral("General")).readEntry("ColorScheme", QString())
                .contains(QStringLiteral("Dark"), Qt::CaseInsensitive) ? QStringLiteral("dark") : QStringLiteral("light");
        }
        if (selection == current) return;
        current = selection;
        Q_EMIT preferenceChanged();
    }
    Q_INVOKABLE bool select(const QString &mode)
    {
        if (mode != QStringLiteral("auto") && mode != QStringLiteral("dark") && mode != QStringLiteral("light")) return false;
        const QString name = QStringLiteral("mac-tahoe-theme-switch");
        QString path = QStandardPaths::findExecutable(name, {QDir::homePath() + QStringLiteral("/.local/bin")});
        if (path.isEmpty()) path = QStandardPaths::findExecutable(name);
        return !path.isEmpty() && QProcess::startDetached(path, {mode});
    }
Q_SIGNALS:
    void preferenceChanged();
private:
    QString stateFile, current;
    QFileSystemWatcher watcher;
};
