// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "input.h"

#include <QHash>
#include <QString>

namespace KWin {

class DisplayCornerInput : public InputEventFilter
{
public:
    DisplayCornerInput();
    void setCorners(const QString &json);
    bool pointerMotion(PointerMotionEvent *event) override;

private:
    struct Corner {
        qreal extent;
        qreal control;

        QPointF project(QPointF point) const;
    };
    QHash<QString, Corner> m_corners;
};

}
