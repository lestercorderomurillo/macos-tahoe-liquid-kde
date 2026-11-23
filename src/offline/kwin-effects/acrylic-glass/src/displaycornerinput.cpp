// SPDX-License-Identifier: GPL-3.0-or-later
#include "displaycornerinput.h"

#include "core/output.h"
#include "effect/effecthandler.h"
#include "effect/effectwindow.h"
#include "input_event.h"
#include "pointer_input.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <algorithm>

namespace KWin {

DisplayCornerInput::DisplayCornerInput()
    : InputEventFilter(InputFilterOrder::WindowSelector)
{
    input()->installInputEventFilter(this);
}

void DisplayCornerInput::setCorners(const QString &json)
{
    m_corners.clear();
    const auto entries = QJsonDocument::fromJson(json.toUtf8()).array();
    if (entries.size() > 64) return;
    for (const auto &entry : entries) {
        const auto corner = entry.toObject();
        const auto output = corner.value(QStringLiteral("output")).toString();
        const qreal extent = corner.value(QStringLiteral("extent")).toDouble();
        const qreal control = corner.value(QStringLiteral("control")).toDouble();
        if (!output.isEmpty() && extent > 0 && extent <= 12 && control > 0 && control < 0.5) {
            m_corners.insert(output, {extent, control});
        }
    }
}

QPointF DisplayCornerInput::Corner::project(QPointF point) const
{
    // Cubic used by the Plasma mask: (extent, 0), (extent*control, 0),
    // (0, extent*control), (0, extent). Coordinates are inward from the edge.
    const auto xAt = [this](qreal t) {
        const qreal rest = 1 - t;
        return extent * rest * rest * (rest + 3 * control * t);
    };

    qreal low = 0;
    qreal high = 1;
    for (int iteration = 0; iteration < 16; ++iteration) {
        const qreal mid = (low + high) / 2;
        if (xAt(mid) > point.x()) low = mid;
        else high = mid;
    }
    if (point.y() + 0.01 >= xAt(1 - (low + high) / 2)) return point;

    // Orthogonal projection preserves motion along the tangent of the curve.
    const auto pointAt = [&](qreal t) { return QPointF(xAt(t), xAt(1 - t)); };
    const auto distance = [&](qreal t) {
        const auto delta = pointAt(t) - point;
        return QPointF::dotProduct(delta, delta);
    };
    low = 0;
    high = 1;
    for (int iteration = 0; iteration < 24; ++iteration) {
        const qreal a = std::lerp(low, high, 1. / 3);
        const qreal b = std::lerp(low, high, 2. / 3);
        if (distance(a) < distance(b)) high = b;
        else low = a;
    }
    return pointAt((low + high) / 2) + QPointF(0.02, 0.02);
}

bool DisplayCornerInput::pointerMotion(PointerMotionEvent *event)
{
    if (m_corners.isEmpty() || effects->isScreenLocked() || input()->pointer()->isConstrained()) return false;

    const auto *screen = effects->screenAt(event->position.toPoint());
    if (!screen) return false;
    const auto corner = m_corners.constFind(screen->name());
    if (corner == m_corners.cend()) return false;

    const auto geometry = screen->geometry();
    const qreal y = event->position.y() - geometry.y();
    const qreal left = event->position.x() - geometry.x();
    const qreal right = geometry.width() - left;
    const qreal x = std::min(left, right);
    if (x < 0 || y < 0 || x >= corner->extent || y >= corner->extent) return false;
    if (const auto *active = effects->activeWindow(); active && active->isFullScreen() && active->screen() == screen) return false;

    const QPointF projected = corner->project({x, y});
    if (projected == QPointF(x, y)) return false;

    const qreal correctedX = left <= right ? projected.x() : geometry.width() - projected.x();
    // KWin defers warps made during input dispatch until the current dispatch
    // ends. Consume the original motion and let the corrected event pass.
    input()->warpPointer(QPointF(geometry.x() + correctedX, geometry.y() + projected.y()));
    return true;
}

}
