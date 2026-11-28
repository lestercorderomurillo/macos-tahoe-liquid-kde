// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "inktransition.h"
#include "glassink.h"
#include "materialsample.h"
#include <QObject>
#include <QPointer>
#include <QRegion>
#include <QJsonObject>
#include <QVariantList>
#include <QWindow>
#include <qqmlregistration.h>

class PopupBackdrop : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QWindow *window READ window WRITE setWindow NOTIFY windowChanged)
    Q_PROPERTY(quint64 backdropRevision READ backdropRevision NOTIFY backdropChanged)
public:
    explicit PopupBackdrop(QObject *parent = nullptr);
    QWindow *window() const { return m_window; }
    virtual void setWindow(QWindow *window);
    quint64 backdropRevision() const { return m_revision; }
    Q_INVOKABLE QColor foregroundAt(QPointF point, QSizeF radius, QColor base, QColor fill) const;
    Q_INVOKABLE QColor animatedForegroundAt(QObject *item, QPointF point, QSizeF radius, QColor base, QColor fill);
    Q_INVOKABLE QColor surfaceForeground(QObject *item, QRectF bounds, QColor reference, QColor base, QColor fill, const QJsonObject &profile, MaterialSample *material);
    Q_INVOKABLE QColor animatedLabelForeground(QObject *item, QPointF point, QSizeF radius, QColor base, QColor fill);
    Q_INVOKABLE QList<QColor> categorySamples(QPointF point, QSizeF radius, QRectF viewport, QColor fill, int count = 5) const;
    Q_INVOKABLE QColor profileGroupForeground(QObject *item, QColor base, const QList<QColor> &surfaces, const QJsonObject &profile);
    Q_INVOKABLE QColor groupForeground(QObject *item, QColor base, const QList<QColor> &surfaces);
    Q_INVOKABLE QColor backdropAt(QPointF point) const;
Q_SIGNALS:
    void backdropChanged();
    void windowChanged();
protected:
    QPointer<QWindow> m_window;
    void notifyBackdropChanged();
private:
    Q_SLOT void movingControlSample(int pid, const QRect &frame, const QString &title);
    Q_SLOT void updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &colors, const QString &title);
    quint64 m_revision = 0;
    QByteArray m_backdropGrid;
    int m_gridSide = 8;
    QRect m_sampleBounds;
    QRect m_lastFrame;
    QRect m_movingFrame;
    GlassInk::Transition m_ink{[this] { ++m_revision; Q_EMIT backdropChanged(); }};
};

class ControlGlass : public PopupBackdrop
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QVariantList surfaces READ surfaces WRITE setSurfaces NOTIFY surfacesChanged)
    Q_PROPERTY(bool maskWindow READ maskWindow WRITE setMaskWindow NOTIFY maskWindowChanged)
public:
    using PopupBackdrop::PopupBackdrop;
    QVariantList surfaces() const { return m_surfaces; }
    bool maskWindow() const { return m_maskWindow; }
    void setMaskWindow(bool enabled);
    void setWindow(QWindow *window) override;
    void setSurfaces(const QVariantList &surfaces);
    // glassOnly skips surfaces marked {glass: false}: they take pointer input
    // but no glass, so a control overlapping a card cannot merge with its shape.
    static QRegion regionFor(const QVariantList &surfaces, bool glassOnly = true);
Q_SIGNALS:
    void surfacesChanged();
    void maskWindowChanged();
protected:
    bool eventFilter(QObject *object, QEvent *event) override;
private:
    void apply();
    QVariantList m_surfaces;
    QRegion m_region;
    QRegion m_inputRegion;
    bool m_maskWindow = true;
    QMetaObject::Connection m_frameConnection;
};
