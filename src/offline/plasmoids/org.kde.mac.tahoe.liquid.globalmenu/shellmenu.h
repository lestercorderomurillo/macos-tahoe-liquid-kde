// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "../org.kde.mac.tahoe.liquid.taskmanager/launcher/glassink.h"
#include <QHash>
#include <QImage>
#include <QMenu>
#include <QPointer>
#include <QScreen>
#include <QStyleOptionMenuItem>

class ShellMenu final : public QMenu
{
    Q_OBJECT
public:
    explicit ShellMenu(QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *event) override;
    void initStyleOption(QStyleOptionMenuItem *option, const QAction *action) const override;

private Q_SLOTS:
    void reloadTinting();
    void updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &grid, const QString &role);

private:
    QImage m_lastMaterial;
    GlassInk::Family m_family = GlassInk::Family::Dark;
    bool m_dynamicTinting = true;
    QByteArray m_grid;
    QRect m_bounds;
    QRect m_sampledGeometry;
    QPointer<QScreen> m_sampledScreen;
    qint64 m_sampledPalette = 0;
    qreal m_sampledScale = 0;
    QHash<const QAction *, QColor> m_rowInks;
};
