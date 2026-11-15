// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QPointer>
#include <QRegion>
#include <QVariantList>
#include <QWindow>
#include <qqmlregistration.h>

// A Control Center is one popup with separate glass islands. Keep compositor
// blur and pointer input confined to those islands, including their round edges.
class ControlGlass : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QWindow *window READ window WRITE setWindow NOTIFY windowChanged)
    Q_PROPERTY(QVariantList surfaces READ surfaces WRITE setSurfaces NOTIFY surfacesChanged)
public:
    explicit ControlGlass(QObject *parent = nullptr) : QObject(parent) {}
    QWindow *window() const { return m_window; }
    QVariantList surfaces() const { return m_surfaces; }
    void setWindow(QWindow *window);
    void setSurfaces(const QVariantList &surfaces);
    static QRegion regionFor(const QVariantList &surfaces);
Q_SIGNALS:
    void windowChanged();
    void surfacesChanged();
protected:
    bool eventFilter(QObject *object, QEvent *event) override;
private:
    void apply();
    QPointer<QWindow> m_window;
    QVariantList m_surfaces;
    QRegion m_region;
    QMetaObject::Connection m_frameConnection;
};
