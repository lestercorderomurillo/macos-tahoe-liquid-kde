// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QComboBox>

class PresetComboBox : public QComboBox
{
    Q_OBJECT
    Q_PROPERTY(int presetValue READ presetValue WRITE setPresetValue NOTIFY presetValueChanged USER true)

public:
    explicit PresetComboBox(QWidget *parent = nullptr)
        : QComboBox(parent)
    {
        connect(this, &QComboBox::currentIndexChanged, this, [this] {
            Q_EMIT presetValueChanged(presetValue());
        });
    }

    int presetValue() const { return currentData().toInt(); }
    void setPresetValue(int value)
    {
        int index = findData(value);
        if (index < 0) {
            value = itemData(0).toInt();
            index = 0;
        }
        // A retired variant uses the remaining edition entry without resetting optics.
        for (int candidate = 0; candidate < count(); ++candidate) {
            if (itemData(candidate).toInt() == value
                && itemData(candidate, Qt::UserRole + 1).toInt() == m_backingTint) {
                index = candidate;
                break;
            }
        }
        setCurrentIndex(index);
    }

    void setBackingTint(int tint)
    {
        const int value = presetValue();
        m_backingTint = tint == 1 ? 1 : 0;
        setPresetValue(value);
    }

private:
    int m_backingTint = 0;

Q_SIGNALS:
    void presetValueChanged(int value);
};
