// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QColor>
#include <QPushButton>

class QMimeData;

class GradientColorButton final : public QPushButton
{
    Q_OBJECT
    Q_PROPERTY(QColor color READ color WRITE setColor NOTIFY colorChanged USER true)
public:
    explicit GradientColorButton(QWidget *parent = nullptr);
    QColor color() const { return m_color; }
    void setColor(const QColor &color);

Q_SIGNALS:
    void colorChanged(const QColor &color);

protected:
    void paintEvent(QPaintEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dropEvent(QDropEvent *event) override;

private:
    QMimeData *colorMimeData() const;
    static QColor readColor(const QMimeData *data);
    QColor m_color;
    QPoint m_pressPosition;
};
