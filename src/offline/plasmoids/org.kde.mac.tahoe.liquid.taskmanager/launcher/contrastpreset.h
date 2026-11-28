// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "glassink.h"
#include <QJsonDocument>
#include <QJsonObject>

namespace ContrastPreset {
using namespace Qt::StringLiterals;

inline QJsonObject defaults()
{
    const auto entry = [](QString scope, int samples, QString correction = u"shift"_s) {
        return QJsonObject{{u"scope"_s, scope}, {u"correction"_s, correction}, {u"sampleCount"_s, samples},
                           {u"maxChannelShift255"_s, 112}, {u"targetSeparationLstar"_s, 33}};
    };
    const auto line = entry(u"line"_s, 15), tile = entry(u"bubble"_s, 15), face = entry(u"component"_s, 15);
    QJsonObject profiles{
        {u"panel.clock"_s, line}, {u"panel.menu"_s, line}, {u"panel.symbol"_s, entry(u"component"_s, 5)},
        {u"controlcenter.tile"_s, tile}, {u"notifications.card"_s, tile},
        {u"launcher.label"_s, line}, {u"launcher.search"_s, tile}, {u"launcher.categories"_s, entry(u"component"_s, 5)},
        {u"menu.options"_s, tile}, {u"menu.native"_s, tile}, {u"about.window"_s, entry(u"component"_s, 45)},
        {u"widget.clock-glass-text"_s, entry(u"letter"_s, 1, u"flip"_s)}, {u"widget.photos"_s, line}
    };
    for (const auto name : {"clock-analog", "clock-analog-2", "clock-analog-3", "clock-square",
                            "city-1", "city-2", "city-3", "city-digital", "timer"})
        profiles.insert(u"widget."_s + QString::fromLatin1(name), face);
    for (const auto name : {"calendar", "music", "weather"})
        profiles.insert(u"widget."_s + QString::fromLatin1(name), tile);
    return profiles;
}

inline QJsonObject empty()
{
    return {{u"version"_s, 1}, {u"extends"_s, u"default"_s}, {u"components"_s, QJsonObject{}}};
}

// Validate the entire document before replacing any part of the active preset.
inline QString resolve(const QJsonObject &document, QJsonObject &resolved)
{
    auto profiles = defaults();
    if (document.value(u"version"_s) != QJsonValue(1)) return u"version"_s;
    if (document.value(u"extends"_s) != QJsonValue(u"default"_s)) return u"extends"_s;
    if (!document.value(u"components"_s).isObject()) return u"components"_s;
    for (const auto &key : document.keys())
        if (!empty().contains(key)) return key;
    const auto components = document.value(u"components"_s).toObject();
    for (auto it = components.begin(); it != components.end(); ++it) {
        if (!profiles.contains(it.key()) || !it.value().isObject()) return it.key();
        auto profile = profiles.value(it.key()).toObject();
        const auto overrides = it.value().toObject();
        for (auto field = overrides.begin(); field != overrides.end(); ++field) {
            const auto key = field.key();
            const auto value = field.value();
            const int integer = value.toInt(-1);
            bool valid = false;
            if (key == u"scope") valid = QStringList{u"letter"_s,u"line"_s,u"bubble"_s,u"component"_s}.contains(value.toString());
            if (key == u"correction") valid = value.toString() == u"shift" || value.toString() == u"flip";
            if (key == u"sampleCount") valid = integer >= 1 && integer <= 256;
            if (key == u"targetSeparationLstar") valid = value.isDouble() && value.toDouble() >= 0 && value.toDouble() <= 100;
            if (key == u"maxChannelShift255") valid = integer >= 0 && integer <= 255;
            if (!valid) return it.key() + u'.' + key;
            profile.insert(key, value);
        }
        if (profile.value(u"scope"_s).toString() == u"letter") {
            if (overrides.contains(u"sampleCount"_s) && overrides.value(u"sampleCount"_s).toInt() != 1)
                return it.key() + u".sampleCount"_s;
            profile.insert(u"sampleCount"_s, 1);
        }
        profiles.insert(it.key(), profile);
    }
    resolved = profiles;
    return {};
}

inline GlassInk::CorrectionSettings settings(const QJsonObject &profile)
{
    return {profile.value(u"correction"_s).toString() == u"flip" ? GlassInk::Correction::Flip : GlassInk::Correction::Shift,
            profile.value(u"targetSeparationLstar"_s).toDouble(33.) / 100.,
            profile.value(u"maxChannelShift255"_s).toInt(112)};
}
}
