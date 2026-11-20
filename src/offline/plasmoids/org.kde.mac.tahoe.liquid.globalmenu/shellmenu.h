// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "../org.kde.mac.tahoe.liquid.taskmanager/launcher/inktransition.h"
#include <QMenu>
#include <QStyleOptionMenuItem>

class ShellMenu final : public QMenu
{
    Q_OBJECT
public:
    explicit ShellMenu(QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *event) override;
    void hideEvent(QHideEvent *event) override;
    void initStyleOption(QStyleOptionMenuItem *option, const QAction *action) const override;

private Q_SLOTS:
    void reloadTinting();
    void updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &grid, const QString &role);

private:
    bool m_dynamicTinting = true;
    QByteArray m_grid;
    QRect m_bounds, m_lastFrame;
    mutable GlassInk::Transition m_ink{[this] { update(); }};
    QHash<const QAction *, QColor> m_rowInks;
};
