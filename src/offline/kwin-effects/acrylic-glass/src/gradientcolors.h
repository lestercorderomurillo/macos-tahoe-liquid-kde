// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QPalette>
#include <QVector4D>

inline const QVector4D &gradientColorForPalette(const QVector4D &light, const QVector4D &dark,
                                               const QPalette &palette)
{
    return palette.color(QPalette::Window).lightnessF() < 0.5 ? dark : light;
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
