// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QColor>
#include <QObject>
#include <QQuickItem>
#include <qqmlregistration.h>

class PanelWallpaper : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(bool watching READ watching WRITE setWatching NOTIFY watchingChanged)
    Q_PROPERTY(quint64 revision READ revision NOTIFY changed)

public:
    explicit PanelWallpaper(QObject *parent = nullptr);
    ~PanelWallpaper() override;
    bool watching() const { return m_watching; }
    void setWatching(bool watching);
    quint64 revision() const { return m_revision; }
    Q_INVOKABLE QColor foregroundAt(QQuickItem *item, int screenNumber, QPointF center, QColor base);
    Q_INVOKABLE static qreal scrimOpacityAt(qreal position);

Q_SIGNALS:
    void changed();
    void watchingChanged();

private:
    void revise();
    int m_screen = -1;
    bool m_watching = false;
    quint64 m_revision = 0;
};
