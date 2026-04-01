/*
    SPDX-FileCopyrightText: 2010 Fredrik Höglund <fredrik@kde.org>
    SPDX-License-Identifier: GPL-2.0-or-later
*/
#include "blur_config.h"
#include "blurconfig.h"

#include <KPluginFactory>
#include "kwineffects_interface.h"

namespace KWin
{

K_PLUGIN_CLASS(LiquidGlassEffectConfig)

LiquidGlassEffectConfig::LiquidGlassEffectConfig(QObject *parent, const KPluginMetaData &data)
    : KCModule(parent, data)
{
    ui.setupUi(widget());
    BlurConfig::instance("kwinrc");
    addConfig(BlurConfig::self(), widget());
}

LiquidGlassEffectConfig::~LiquidGlassEffectConfig()
{
}

void LiquidGlassEffectConfig::save()
{
    KCModule::save();

    OrgKdeKwinEffectsInterface interface(QStringLiteral("org.kde.KWin"),
                                         QStringLiteral("/Effects"),
                                         QDBusConnection::sessionBus());

    if (QGuiApplication::platformName() == QStringLiteral("xcb")) {
        interface.reconfigureEffect(QStringLiteral("liquidglass_x11"));
    } else {
        interface.reconfigureEffect(QStringLiteral("liquidglass"));
    }
}

} // namespace KWin

#include "blur_config.moc"
#include "moc_blur_config.cpp"
