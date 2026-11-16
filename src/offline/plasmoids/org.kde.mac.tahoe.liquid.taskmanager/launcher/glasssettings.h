// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QPointer>
#include <QWindow>
#include <qqmlregistration.h>

// The same material settings drive the compositor and client-side background
// fills. This object never applies opacity to a whole window or its contents.
class GlassSettings : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString component READ component WRITE setComponent NOTIFY changed)
    Q_PROPERTY(QWindow *window READ window WRITE setWindow NOTIFY changed)
    Q_PROPERTY(qreal lightOpacity READ lightOpacity NOTIFY changed)
    Q_PROPERTY(qreal darkOpacity READ darkOpacity NOTIFY changed)
public:
    explicit GlassSettings(QObject *parent = nullptr);
    QString component() const { return m_component; }
    QWindow *window() const { return m_window; }
    void setComponent(const QString &component);
    void setWindow(QWindow *window);
    qreal lightOpacity() const;
    qreal darkOpacity() const;
Q_SIGNALS:
    void changed();
private:
    qreal opacity(const QString &key) const;
    QString m_component;
    QPointer<QWindow> m_window;
};
