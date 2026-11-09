// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QObject>
#include <QKeySequence>
#include <memory>

class MenuShortcutSender : public QObject
{
    Q_OBJECT
public:
    explicit MenuShortcutSender(QObject *parent = nullptr);
    ~MenuShortcutSender() override;
    bool available() const;
    bool send(const QKeySequence &sequence);
Q_SIGNALS:
    void availabilityChanged();
private:
    class Private;
    std::unique_ptr<Private> d;
};
