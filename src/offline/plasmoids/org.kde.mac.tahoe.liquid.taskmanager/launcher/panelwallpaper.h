// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QObject>
#include <QQuickWindow>
#include <qqmlregistration.h>

class PanelWallpaper : public QObject
{
    Q_OBJECT
    QML_ELEMENT
public:
    using QObject::QObject;
    Q_INVOKABLE QObject *sourceFor(QQuickWindow *window, QObject *containment) const;
    Q_INVOKABLE static qreal scrimOpacityAt(qreal position);
};
