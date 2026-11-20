// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QPalette>
#include <QVector4D>

inline const QVector4D &gradientColorForPalette(const QVector4D &light, const QVector4D &dark,
                                               const QPalette &palette)
{
    return palette.color(QPalette::Window).lightnessF() < 0.5 ? dark : light;
}

// Premultiplied gradient stops and smoothstep match the glass fragment shaders.
inline QVector4D gradientOverlayAt(float height, float centerPosition, const QVector4D &top,
                                   const QVector4D &center, const QVector4D &bottom)
{
    const bool upper = height < centerPosition;
    const auto &start = upper ? top : center;
    const auto &end = upper ? center : bottom;
    const float length = upper ? centerPosition : 1.f - centerPosition;
    float t = qBound(0.f, (height - (upper ? 0.f : centerPosition)) / qMax(length, .000001f), 1.f);
    t = t * t * (3.f - 2.f * t);
    return QVector4D(start.toVector3D() * start.w() * (1.f - t) + end.toVector3D() * end.w() * t,
                     start.w() * (1.f - t) + end.w() * t);
}

inline bool gradientEnabledForSurface(bool enabled, bool dock, const QString &resourceClass,
                                      const QString &caption)
{
    return enabled && !dock && !((resourceClass == QStringLiteral("plasmashell")
        || resourceClass == QStringLiteral("org.kde.plasmashell"))
        && caption == QStringLiteral("mttkde-control-center"));
}

inline bool isProjectNotification(const QString &resourceClass, const QString &caption)
{
    return caption == QStringLiteral("mttkde-notifications")
        && (resourceClass == QStringLiteral("plasmashell") || resourceClass == QStringLiteral("org.kde.plasmashell"));
}
