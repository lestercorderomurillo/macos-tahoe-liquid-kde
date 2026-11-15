// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <PlasmaQuick/PopupPlasmaWindow>
#include <QPointer>
#include <QList>
#include <qqmlregistration.h>

// A separate native frame keeps the capsule's glass, input mask and shadow aligned.
class LauncherSearchPopup : public PlasmaQuick::PopupPlasmaWindow
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QWindow *focusWindow READ focusWindow NOTIFY focusWindowChanged)

public:
    LauncherSearchPopup();
    Q_INVOKABLE void activate() { requestActivate(); }
    QWindow *focusWindow() const;

protected:
    bool event(QEvent *event) override;
    bool eventFilter(QObject *watched, QEvent *event) override;

Q_SIGNALS:
    void focusWindowChanged();

private:
    QPointer<QWindow> m_anchorWindow;
    QList<QMetaObject::Connection> m_anchorGeometryConnections;
};
