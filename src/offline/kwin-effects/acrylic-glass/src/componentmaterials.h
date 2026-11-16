// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <KConfigGroup>
#include <QColor>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStringList>
#include <cmath>

namespace GlassMaterials {
inline const QStringList components = {QStringLiteral("general"), QStringLiteral("finder"),
    QStringLiteral("menus"), QStringLiteral("popups"), QStringLiteral("apps"), QStringLiteral("search"),
    QStringLiteral("control-center"), QStringLiteral("about"), QStringLiteral("dock"), QStringLiteral("panel")};

inline QJsonObject merge(QJsonObject base, const QJsonObject &overrides)
{
    for (auto i = overrides.begin(); i != overrides.end(); ++i) base.insert(i.key(), i.value());
    return base;
}

inline QJsonObject defaults(const QJsonObject &preset, bool tinted)
{
    auto base = preset.value(QStringLiteral("values")).toObject();
    if (tinted) base = merge(base, preset.value(QStringLiteral("tinted_values")).toObject());
    QJsonObject result;
    const auto overrides = preset.value(QStringLiteral("components")).toObject();
    for (const auto &component : components)
        result.insert(component, merge(base, overrides.value(component).toObject()));
    return result;
}

inline QJsonObject readLegacy(const KConfigGroup &group, QJsonObject values)
{
    for (auto i = values.begin(); i != values.end(); ++i) {
        if (i.value().isBool()) i.value() = group.readEntry(i.key(), i.value().toBool());
        else if (i.value().isDouble()) i.value() = group.readEntry(i.key(), i.value().toDouble());
        else i.value() = group.readEntry(i.key(), QColor(i.value().toString())).name(QColor::HexRgb);
    }
    for (const QString stop : {QStringLiteral("Top"), QStringLiteral("Center"), QStringLiteral("Bottom")}) {
        const auto dark = QStringLiteral("Gradient") + stop + QStringLiteral("DarkColor");
        if (!group.hasKey(dark)) values[dark] = values.value(QStringLiteral("Gradient") + stop + QStringLiteral("Color"));
    }
    return values;
}

// Missing component settings inherit the old active material, including user
// overrides. Dock and Control Center retain their historical exceptions.
inline QJsonObject read(const KConfigGroup &group, const QJsonObject &preset, bool tinted, const QJsonObject &legacyDefaults)
{
    Q_UNUSED(tinted);
    const auto legacy = readLegacy(group, legacyDefaults);
    const auto saved = QJsonDocument::fromJson(group.readEntry("ComponentMaterials", QString()).toUtf8()).object();
    const auto exceptions = preset.value(QStringLiteral("components")).toObject();
    QJsonObject result;
    for (const auto &component : components) {
        auto values = merge(legacy, exceptions.value(component).toObject());
        // General remains in its historical keys for existing installers and tools.
        if (component != QStringLiteral("general")) values = merge(values, saved.value(component).toObject());
        result.insert(component, values);
    }
    return result;
}

inline double number(const QJsonObject &v, const char *key, double fallback, double lo, double hi)
{
    const double value = v.value(QLatin1String(key)).toDouble(fallback);
    return std::isfinite(value) ? qBound(lo, value, hi) : fallback;
}

inline QString classify(const QString &resource, const QString &caption, bool dock, bool popup, bool applet,
                        const QString &aboutTitle)
{
    const QString name = resource.toLower();
    if (name == QStringLiteral("plasmashell") || name == QStringLiteral("org.kde.plasmashell")) {
        if (caption == QStringLiteral("mttkde-control-center")) return QStringLiteral("control-center");
        if (caption == QStringLiteral("mttkde-apps")) return QStringLiteral("apps");
        if (caption == QStringLiteral("mttkde-search")) return QStringLiteral("search");
        if (caption == aboutTitle || caption == QStringLiteral("About This Computer")) return QStringLiteral("about");
    }
    if (dock) return caption == QStringLiteral("mttkde-dock") ? QStringLiteral("dock") : QStringLiteral("panel");
    if (applet && (name == QStringLiteral("plasmashell") || name == QStringLiteral("org.kde.plasmashell"))) return QStringLiteral("popups");
    if (popup || applet) return QStringLiteral("menus");
    if (name == QStringLiteral("dolphin") || name == QStringLiteral("org.kde.dolphin")
        || name == QStringLiteral("nautilus") || name == QStringLiteral("org.gnome.nautilus")) return QStringLiteral("finder");
    return QStringLiteral("general");
}
}
