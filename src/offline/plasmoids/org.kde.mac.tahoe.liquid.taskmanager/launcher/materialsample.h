// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QQuickItem>
#include <QQuickItemGrabResult>
#include <QQuickWindow>
#include <QPointer>
#include <QTimer>
#include <QFont>
#include <QVariantList>
#include <qqmlregistration.h>

// Capture a background-only item. Siblings that paint text never enter this image.
class MaterialSample : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QQuickItem *source READ source WRITE setSource NOTIFY sourceChanged)
    Q_PROPERTY(quint64 revision READ revision NOTIFY changed)
public:
    explicit MaterialSample(QObject *parent = nullptr);
    QQuickItem *source() const { return m_source; }
    void setSource(QQuickItem *source);
    quint64 revision() const { return m_revision; }
    void findWindowFrame(QQuickWindow *window, const QString &name);
    Q_INVOKABLE QColor at(QPointF scenePoint) const;
    Q_SLOT void invalidate();
    Q_INVOKABLE QList<QColor> smoothGlyphColors(const QList<QColor> &colors) const;
    Q_INVOKABLE static QVariantList textRuns(const QString &text, const QFont &font, qreal width, int wrapMode, int alignment, bool letters);
Q_SIGNALS:
    void changed();
    void sourceChanged();
private:
    void capture();
    QPointer<QQuickItem> m_source;
    QSharedPointer<QQuickItemGrabResult> m_pending;
    QTimer m_timer;
    QImage m_pixels;
    quint64 m_revision = 0;
    bool m_dirty = false;
};
