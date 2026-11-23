// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "inktransition.h"
#include <QObject>
#include <QPointer>
#include <QSizeF>
#include <QWindow>
#include <QVariantList>
#include <qqmlregistration.h>

// The same material settings drive the compositor and client-side background
// fills. This object never applies opacity to a whole window or its contents.
class GlassSettings : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString component READ component WRITE setComponent NOTIFY changed)
    Q_PROPERTY(QWindow *window READ window WRITE setWindow NOTIFY changed)
    Q_PROPERTY(QSizeF displayCorners READ displayCorners WRITE setDisplayCorners NOTIFY changed)
    Q_PROPERTY(QString frameSource READ frameSource WRITE setFrameSource NOTIFY changed)
    Q_PROPERTY(quint64 inkRevision READ inkRevision NOTIFY inkChanged)
    Q_PROPERTY(bool dynamicTinting READ dynamicTinting NOTIFY changed)
    Q_PROPERTY(qreal lightOpacity READ lightOpacity NOTIFY changed)
    Q_PROPERTY(qreal darkOpacity READ darkOpacity NOTIFY changed)
public:
    explicit GlassSettings(QObject *parent = nullptr);
    ~GlassSettings() override;
    QSizeF displayCorners() const { return m_displayCorners; }
    void setDisplayCorners(QSizeF geometry);
    QString component() const { return m_component; }
    QWindow *window() const { return m_window; }
    QString frameSource() const { return m_frameSource; }
    void setFrameSource(const QString &source);
    void setComponent(const QString &component);
    void setWindow(QWindow *window);
    bool dynamicTinting() const;
    quint64 inkRevision() const { return m_inkRevision; }
    Q_INVOKABLE QColor animatedNotificationForeground(QObject *item, QWindow *window, QColor base, QColor backdrop, QColor fill);
    Q_INVOKABLE QColor notificationForeground(QColor base, QColor backdrop, QColor fill) const;
    qreal lightOpacity() const;
    qreal darkOpacity() const;
Q_SIGNALS:
    void changed();
    void inkChanged();
private:
    quint64 m_inkRevision = 0;
    GlassInk::Transition m_ink{[this] { ++m_inkRevision; Q_EMIT inkChanged(); }};
    qreal opacity(const QString &key) const;
    QString m_component;
    QString m_frameSource;
    QPointer<QWindow> m_window;
    QSizeF m_displayCorners;
};
