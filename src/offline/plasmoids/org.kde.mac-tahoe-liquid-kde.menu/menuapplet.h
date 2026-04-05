/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include <Plasma/Applet>
#include <QPointer>

class QQuickItem;
class QMenu;

class MenuApplet : public Plasma::Applet
{
    Q_OBJECT

public:
    explicit MenuApplet(QObject *parent, const KPluginMetaData &data, const QVariantList &args);
    ~MenuApplet() override;

Q_SIGNALS:
    void aboutRequested();

public Q_SLOTS:
    void trigger(QQuickItem *ctx);

private:
    QPointer<QMenu> m_currentMenu;
};
