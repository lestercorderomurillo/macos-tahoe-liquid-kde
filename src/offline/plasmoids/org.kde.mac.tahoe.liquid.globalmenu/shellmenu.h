// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

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
    void updateBackdrop(int pid, const QRect &frame, const QRect &bounds, const QByteArray &grid, const QString &role);

private:
    QByteArray m_grid;
    QRect m_bounds;
    QHash<const QAction *, QColor> m_rowBackgrounds;
};
