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
    Q_PROPERTY(quint64 backdropRevision READ backdropRevision NOTIFY backdropChanged)
    Q_PROPERTY(bool maskWindow READ maskWindow WRITE setMaskWindow NOTIFY maskWindowChanged)
public:
    explicit ControlGlass(QObject *parent = nullptr);
    QWindow *window() const { return m_window; }
    QVariantList surfaces() const { return m_surfaces; }
    quint64 backdropRevision() const { return m_revision; }
    Q_INVOKABLE QColor backdropAt(QPointF point) const;
    bool maskWindow() const { return m_maskWindow; }
    void setMaskWindow(bool enabled);
    void setWindow(QWindow *window);
    void setSurfaces(const QVariantList &surfaces);
    static QRegion regionFor(const QVariantList &surfaces);
Q_SIGNALS:
    void backdropChanged();
    void windowChanged();
    void surfacesChanged();
    void maskWindowChanged();
protected:
    bool eventFilter(QObject *object, QEvent *event) override;
private:
    Q_SLOT void updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &colors);
    void apply();
    quint64 m_revision = 0;
    QByteArray m_backdropGrid;
    QRect m_sampleBounds;
    QPointer<QWindow> m_window;
    QVariantList m_surfaces;
    QRegion m_region;
    bool m_maskWindow = true;
    QMetaObject::Connection m_frameConnection;
};
