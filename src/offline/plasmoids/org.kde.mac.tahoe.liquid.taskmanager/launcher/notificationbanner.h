/*
  SPDX-FileCopyrightText: 2024 David Edmundson <davidedmundson@kde.org>
  SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL
*/

#pragma once

#include <QQuickWindow>
#include <QQuickItem>
#include <QPointer>

class NotificationBanner : public QQuickWindow
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QQuickItem *mainItem READ mainItem WRITE setMainItem NOTIFY mainItemChanged)
    Q_PROPERTY(bool takeFocus READ takeFocus WRITE setTakeFocus NOTIFY takeFocusChanged)
    Q_PROPERTY(bool isCritical READ isCritical WRITE setIsCritical NOTIFY isCriticalChanged FINAL)
public:
    NotificationBanner();
    ~NotificationBanner() override;

    QQuickItem *mainItem() const;
    void setMainItem(QQuickItem *item);

    bool takeFocus() const;
    void setTakeFocus(bool takeFocus);

    bool isCritical() const;
    void setIsCritical(bool critical);

protected:
    bool event(QEvent *e) override;
    void moveEvent(QMoveEvent *) override;
Q_SIGNALS:
    void mainItemChanged();
    void takeFocusChanged();
    void isCriticalChanged();

private:
    QPointer<QQuickItem> m_mainItem;
    bool m_takeFocus = false;
    bool m_critical = false;
};
